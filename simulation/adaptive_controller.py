"""
Smart Route — Adaptive Traffic Signal Controller
=================================================
Algorithm : Webster's method
           Dynamically adjusts green split between NS and EW phases
           based on real-time queue lengths sampled via TraCI.

Usage
-----
  python3 adaptive_controller.py [--gui] [--fixed] [--no-viz]

  --gui     : Launch sumo-gui instead of headless sumo
  --fixed   : Run fixed-time baseline only (no adaptive)
  --no-viz  : Skip matplotlib dashboard after simulation
"""

import os
import sys
import json
import argparse
import statistics
import traci
import traci.constants as tc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUMO_CFG   = "intersection.sumocfg"
TLS_ID     = "center"

MIN_GREEN       = 10
MAX_GREEN       = 60
YELLOW_DURATION =  3
LOST_TIME       =  4

NS_LANES = ["north_in_0", "north_in_1", "south_in_0", "south_in_1"]
EW_LANES = ["east_in_0",  "east_in_1",  "west_in_0",  "west_in_1"]

CONTROL_INTERVAL = 30
SIM_DURATION     = 3600

# ---------------------------------------------------------------------------
# TLS helpers
# ---------------------------------------------------------------------------

def read_tls_program():
    all_programs = traci.trafficlight.getAllProgramLogics(TLS_ID)
    logic  = all_programs[0]
    phases = logic.getPhases()
    green_idx  = [i for i, ph in enumerate(phases) if "g" in ph.state.lower() and "y" not in ph.state.lower()]
    return logic, phases, green_idx


def apply_green_times(base_logic, base_phases, green_idx, g_times):
    new_phases = []
    gi = 0
    for i, ph in enumerate(base_phases):
        dur = g_times[gi] if i in green_idx and gi < len(g_times) else ph.duration
        if i in green_idx:
            gi += 1
        new_phases.append(traci.trafficlight.Phase(dur, ph.state, ph.minDur, ph.maxDur))

    new_logic = traci.trafficlight.Logic(
        programID="adaptive",
        type=base_logic.type,
        currentPhaseIndex=traci.trafficlight.getPhase(TLS_ID),
        phases=new_phases,
    )
    traci.trafficlight.setProgramLogic(TLS_ID, new_logic)
    traci.trafficlight.setProgram(TLS_ID, "adaptive")

# ---------------------------------------------------------------------------
# Webster split
# ---------------------------------------------------------------------------

def webster_green_split(q_ns, q_ew):
    if q_ns == 0 and q_ew == 0:
        return MIN_GREEN, MIN_GREEN
    total = q_ns + q_ew
    y1, y2 = q_ns / total, q_ew / total
    L     = 2 * LOST_TIME
    Y     = min(y1 + y2, 0.9)
    C_opt = (1.5 * L + 5) / max(1 - Y, 0.10)
    C_opt = max(30, min(C_opt, (MAX_GREEN + YELLOW_DURATION) * 2))
    avail = C_opt - 2 * (YELLOW_DURATION + LOST_TIME)
    g1 = max(MIN_GREEN, min(MAX_GREEN, int(avail * y1)))
    g2 = max(MIN_GREEN, min(MAX_GREEN, int(avail * y2)))
    return g1, g2

# ---------------------------------------------------------------------------
# Queue helper
# ---------------------------------------------------------------------------

def get_queue(lanes):
    return sum(traci.lane.getLastStepHaltingNumber(l) for l in lanes)

def get_speed(lanes):
    speeds = [traci.lane.getLastStepMeanSpeed(l) for l in lanes]
    return round(statistics.mean(speeds), 2) if speeds else 0

# ---------------------------------------------------------------------------
# Simulation runners
# ---------------------------------------------------------------------------

def run_simulation(sumo_binary, adaptive=True):
    label = "adaptive" if adaptive else "fixed"
    sumo_cmd = [sumo_binary, "-c", SUMO_CFG,
                "--no-warnings", "--time-to-teleport", "-1"]
    traci.start(sumo_cmd)
    traci.simulation.subscribe([tc.VAR_ARRIVED_VEHICLES_IDS,
                                 tc.VAR_DEPARTED_VEHICLES_IDS])

    if adaptive:
        base_logic, base_phases, green_idx = read_tls_program()
        g_times = [ph.duration for i, ph in enumerate(base_phases) if i in green_idx]

    # Data collection
    data = {
        "label"        : label,
        "steps"        : [],
        "q_ns"         : [],
        "q_ew"         : [],
        "q_total"      : [],
        "throughput"   : [],
        "green_ns"     : [],
        "green_ew"     : [],
        "speed_ns"     : [],
        "speed_ew"     : [],
    }

    step         = 0
    last_control = -CONTROL_INTERVAL
    arrived_set  = set()
    throughput   = 0
    g_ns_cur     = 42   # netconvert defaults
    g_ew_cur     = 42

    try:
        while step < SIM_DURATION:
            traci.simulationStep()

            sub = traci.simulation.getSubscriptionResults()
            for vid in sub.get(tc.VAR_ARRIVED_VEHICLES_IDS, []):
                if vid not in arrived_set:
                    arrived_set.add(vid)
                    throughput += 1

            q_ns  = get_queue(NS_LANES)
            q_ew  = get_queue(EW_LANES)
            sp_ns = get_speed(NS_LANES)
            sp_ew = get_speed(EW_LANES)

            if adaptive and step - last_control >= CONTROL_INTERVAL:
                g_ns_cur, g_ew_cur = webster_green_split(q_ns, q_ew)
                apply_green_times(base_logic, base_phases, green_idx,
                                  [g_ns_cur, g_ew_cur])
                last_control = step
                print(f"  [t={step:4d}s] Q_NS={q_ns:3d} Q_EW={q_ew:3d} "
                      f"→ green NS={g_ns_cur}s EW={g_ew_cur}s")

            # Record every 10 steps for lighter data
            if step % 10 == 0:
                data["steps"].append(step)
                data["q_ns"].append(q_ns)
                data["q_ew"].append(q_ew)
                data["q_total"].append(q_ns + q_ew)
                data["throughput"].append(throughput)
                data["green_ns"].append(g_ns_cur)
                data["green_ew"].append(g_ew_cur)
                data["speed_ns"].append(sp_ns)
                data["speed_ew"].append(sp_ew)

            step += 1
    finally:
        traci.close()

    data["final_throughput"] = throughput
    data["avg_queue"] = round(statistics.mean(data["q_total"]), 2) if data["q_total"] else 0
    data["max_queue"] = max(data["q_total"]) if data["q_total"] else 0

    return data

# ---------------------------------------------------------------------------
# Visualization dashboard
# ---------------------------------------------------------------------------

def visualize(fixed_data, adaptive_data):
    import matplotlib
    matplotlib.use("Agg")   # no display needed — saves to file
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.gridspec import GridSpec

    steps_f = fixed_data["steps"]
    steps_a = adaptive_data["steps"]

    fig = plt.figure(figsize=(18, 12), facecolor="#0f1117")
    fig.suptitle("Smart Route — Adaptive vs Fixed-Time Traffic Control",
                 color="white", fontsize=18, fontweight="bold", y=0.98)

    gs = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    C_ADAPT  = "#00d4ff"
    C_FIXED  = "#ff6b6b"
    C_NS     = "#ffd166"
    C_EW     = "#06d6a0"
    BG       = "#1a1d2e"
    GRID_CLR = "#2a2d3e"

    def styled_ax(ax, title):
        ax.set_facecolor(BG)
        ax.tick_params(colors="white", labelsize=8)
        ax.set_title(title, color="white", fontsize=10, fontweight="bold", pad=8)
        ax.spines[:].set_color(GRID_CLR)
        ax.grid(color=GRID_CLR, linewidth=0.6)
        ax.yaxis.label.set_color("white")
        ax.xaxis.label.set_color("white")

    # ── 1. Total queue over time ────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :2])
    styled_ax(ax1, "📊 Total Queue Length Over Time")
    ax1.plot(steps_f, fixed_data["q_total"],    color=C_FIXED,  alpha=0.8,
             linewidth=1.5, label="Fixed-Time")
    ax1.plot(steps_a, adaptive_data["q_total"], color=C_ADAPT, alpha=0.9,
             linewidth=1.5, label="Webster Adaptive")
    ax1.fill_between(steps_a, adaptive_data["q_total"], alpha=0.1, color=C_ADAPT)
    ax1.set_xlabel("Simulation Time (s)")
    ax1.set_ylabel("Vehicles Waiting")
    ax1.legend(facecolor=BG, labelcolor="white", framealpha=0.9)

    # ── 2. Cumulative throughput ────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 2])
    styled_ax(ax2, "🚗 Cumulative Throughput")
    ax2.plot(steps_f, fixed_data["throughput"],    color=C_FIXED,  linewidth=1.5, label="Fixed")
    ax2.plot(steps_a, adaptive_data["throughput"], color=C_ADAPT, linewidth=1.5, label="Adaptive")
    ax2.set_xlabel("Simulation Time (s)")
    ax2.set_ylabel("Vehicles Completed")
    ax2.legend(facecolor=BG, labelcolor="white", framealpha=0.9)

    # ── 3. NS vs EW queue (adaptive only) ──────────────────────────────────
    ax3 = fig.add_subplot(gs[1, :2])
    styled_ax(ax3, "🔀 NS vs EW Queue (Adaptive Controller)")
    ax3.plot(steps_a, adaptive_data["q_ns"], color=C_NS,  linewidth=1.2, label="North-South")
    ax3.plot(steps_a, adaptive_data["q_ew"], color=C_EW,  linewidth=1.2, label="East-West")
    ax3.fill_between(steps_a, adaptive_data["q_ns"], alpha=0.12, color=C_NS)
    ax3.fill_between(steps_a, adaptive_data["q_ew"], alpha=0.12, color=C_EW)
    ax3.set_xlabel("Simulation Time (s)")
    ax3.set_ylabel("Vehicles Waiting")
    ax3.legend(facecolor=BG, labelcolor="white", framealpha=0.9)

    # ── 4. Green time allocation ────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 2])
    styled_ax(ax4, "🟢 Webster Green Split Over Time")
    ax4.plot(steps_a, adaptive_data["green_ns"], color=C_NS,  linewidth=1.2, label="NS Green (s)")
    ax4.plot(steps_a, adaptive_data["green_ew"], color=C_EW,  linewidth=1.2, label="EW Green (s)")
    ax4.axhline(42, color="white", linestyle="--", alpha=0.4, linewidth=1, label="Fixed (42s)")
    ax4.set_xlabel("Simulation Time (s)")
    ax4.set_ylabel("Green Duration (s)")
    ax4.set_ylim(0, MAX_GREEN + 10)
    ax4.legend(facecolor=BG, labelcolor="white", framealpha=0.9, fontsize=8)

    # ── 5. KPI summary cards ────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_facecolor(BG)
    ax5.axis("off")
    ax5.set_title("📋 Key Performance Indicators", color="white",
                  fontsize=11, fontweight="bold", loc="left", pad=10)

    kpis = [
        ("Avg Queue\n(vehicles)",
         fixed_data["avg_queue"],    adaptive_data["avg_queue"],    True),
        ("Peak Queue\n(vehicles)",
         fixed_data["max_queue"],    adaptive_data["max_queue"],    True),
        ("Total Vehicles\nCompleted",
         fixed_data["final_throughput"], adaptive_data["final_throughput"], False),
    ]

    card_width  = 0.28
    card_height = 0.70
    card_y      = 0.12
    xs          = [0.04, 0.36, 0.68]

    for (label, fv, av, lower_better), x in zip(kpis, xs):
        if fv != 0:
            pct  = (av - fv) / fv * 100
            improved = (pct < 0) == lower_better
            arrow = "▼" if pct < 0 else "▲"
            col   = "#00ff88" if improved else "#ff4444"
            delta = f"{arrow} {abs(pct):.1f}%"
        else:
            col, delta = "white", "—"

        rect = mpatches.FancyBboxPatch((x, card_y), card_width, card_height,
                                        boxstyle="round,pad=0.01",
                                        transform=ax5.transAxes,
                                        facecolor="#252840", edgecolor=GRID_CLR,
                                        linewidth=1.5, clip_on=False)
        ax5.add_patch(rect)

        ax5.text(x + card_width / 2, card_y + card_height - 0.06, label,
                 ha="center", va="top", color="#aaaacc",
                 fontsize=9, transform=ax5.transAxes, fontweight="bold")

        ax5.text(x + card_width / 2, card_y + card_height / 2 + 0.04,
                 f"Fixed: {fv}", ha="center", va="center",
                 color=C_FIXED, fontsize=11, fontweight="bold",
                 transform=ax5.transAxes)

        ax5.text(x + card_width / 2, card_y + card_height / 2 - 0.12,
                 f"Adaptive: {av}", ha="center", va="center",
                 color=C_ADAPT, fontsize=11, fontweight="bold",
                 transform=ax5.transAxes)

        ax5.text(x + card_width / 2, card_y + 0.04, delta,
                 ha="center", va="bottom", color=col,
                 fontsize=13, fontweight="bold", transform=ax5.transAxes)

    out_path = "simulation_results.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n  📊 Dashboard saved → {out_path}")
    return out_path

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui",    action="store_true")
    parser.add_argument("--fixed",  action="store_true")
    parser.add_argument("--no-viz", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("SUMO_HOME", "/opt/homebrew/opt/sumo/share/sumo")
    sumo_binary = "sumo-gui" if args.gui else "sumo"

    adaptive_data = fixed_data = None

    if not args.fixed:
        print("\n▶  Running Webster Adaptive controller (3600 sim-seconds)...")
        adaptive_data = run_simulation(sumo_binary, adaptive=True)
        print(f"   ✓ Throughput: {adaptive_data['final_throughput']} veh  |  "
              f"Avg Queue: {adaptive_data['avg_queue']} veh")

    print("\n▶  Running Fixed-Time baseline...")
    fixed_data = run_simulation(sumo_binary, adaptive=False)
    print(f"   ✓ Throughput: {fixed_data['final_throughput']} veh  |  "
          f"Avg Queue: {fixed_data['avg_queue']} veh")

    # Save JSON data
    with open("results.json", "w") as f:
        json.dump({"fixed": fixed_data, "adaptive": adaptive_data}, f)

    # Print terminal summary
    if fixed_data and adaptive_data:
        w = 60
        print(f"\n{'═'*w}")
        print(f"  {'SMART ROUTE — Results':^{w-2}}")
        print(f"{'═'*w}")
        print(f"  {'Metric':<24} {'Fixed':>10} {'Adaptive':>10} {'Change':>10}")
        print(f"  {'-'*54}")
        for label, fk, ak, low in [
            ("Avg Queue (veh)",   "avg_queue",        "avg_queue",        True),
            ("Peak Queue (veh)",  "max_queue",        "max_queue",        True),
            ("Throughput (veh)",  "final_throughput", "final_throughput", False),
        ]:
            fv, av = fixed_data[fk], adaptive_data[ak]
            pct  = (av - fv) / fv * 100 if fv else 0
            good = (pct < 0) == low
            sym  = ("✅" if good else "❌")
            print(f"  {label:<24} {str(fv):>10} {str(av):>10} "
                  f"{'▼' if pct<0 else '▲'}{abs(pct):.1f}% {sym}")
        print(f"{'═'*w}\n")

    # Generate visualization
    if not args.no_viz and fixed_data and adaptive_data:
        visualize(fixed_data, adaptive_data)


if __name__ == "__main__":
    main()
