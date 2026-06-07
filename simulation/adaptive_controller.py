"""
SMART_ROUTE - Adaptive Signal Controller for SUMO
Replaces fixed-time signals with AI-driven adaptive control
"""

import os
import sys
import traci
import time
import requests
from collections import defaultdict

# Add SUMO tools to path
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.exit("Please set SUMO_HOME environment variable")

# ============ CONFIG ============
SUMO_BINARY = "sumo"  # changed to headless to avoid X11 errors
CONFIG_FILE = "intersection.sumocfg"
BACKEND_URL = "http://localhost:8000"
INTERSECTION_ID = "intersection_1"
SEND_TO_BACKEND = True

# Signal control params
MIN_GREEN_TIME = 10
MAX_GREEN_TIME = 60
YELLOW_TIME = 3
DETECTION_RANGE = 100  # meters from junction

# Traffic light ID (from network file, junction "center")
TL_ID = "center"
# ================================


class AdaptiveSignalController:
    """
    Smart traffic signal that adapts based on real-time vehicle counts.
    
    Phases for 4-way intersection:
    - Phase 0: GREEN for N-S | RED for E-W
    - Phase 1: YELLOW for N-S | RED for E-W (transition)
    - Phase 2: RED for N-S | GREEN for E-W
    - Phase 3: RED for N-S | YELLOW for E-W (transition)
    """
    
    def __init__(self):
        self.current_phase = 0  # 0 = NS green, 2 = EW green
        self.phase_start_time = 0
        self.is_yellow = False
        self.stats = {
            "decisions_made": 0,
            "ns_phase_count": 0,
            "ew_phase_count": 0,
            "total_vehicles_served": 0,
            "avg_wait_times": []
        }
    
    def get_vehicle_counts(self):
        """Count waiting vehicles per direction"""
        counts = defaultdict(int)
        
        # Get all vehicles in simulation
        for veh_id in traci.vehicle.getIDList():
            edge = traci.vehicle.getRoadID(veh_id)
            speed = traci.vehicle.getSpeed(veh_id)
            
            # Only count waiting/slow vehicles near intersection
            # pyrefly: ignore [unsupported-operation]
            if speed < 5:  # m/s threshold
                if "north_in" in edge:
                    counts["north"] += 1
                elif "south_in" in edge:
                    counts["south"] += 1
                elif "east_in" in edge:
                    counts["east"] += 1
                elif "west_in" in edge:
                    counts["west"] += 1
        
        counts["ns_total"] = counts["north"] + counts["south"]
        counts["ew_total"] = counts["east"] + counts["west"]
        counts["total"] = counts["ns_total"] + counts["ew_total"]
        
        return dict(counts)
    
    def decide_phase(self, counts, current_time):
        """Decide if signal should change"""
        time_in_phase = current_time - self.phase_start_time
        
        # Don't switch during yellow phase
        if self.current_phase in [1, 3]:
            if time_in_phase >= YELLOW_TIME:
                # Yellow done, move to next green
                self.current_phase = (self.current_phase + 1) % 4
                self.phase_start_time = current_time
                self.stats["decisions_made"] += 1
                return self.current_phase
            return self.current_phase
        
        # Force switch if max time exceeded
        if time_in_phase >= MAX_GREEN_TIME:
            self._transition_to_yellow(current_time)
            return self.current_phase
        
        # Smart switch (after minimum time)
        if time_in_phase >= MIN_GREEN_TIME:
            if self.current_phase == 0:  # NS green
                # Switch if EW has significantly more traffic
                if counts["ew_total"] > counts["ns_total"] + 3:
                    self._transition_to_yellow(current_time)
            elif self.current_phase == 2:  # EW green
                if counts["ns_total"] > counts["ew_total"] + 3:
                    self._transition_to_yellow(current_time)
        
        return self.current_phase
    
    def _transition_to_yellow(self, current_time):
        """Move to yellow phase"""
        self.current_phase += 1  # 0→1 or 2→3
        self.phase_start_time = current_time
        self.stats["decisions_made"] += 1
    
    def apply_phase(self, phase):
        """Apply phase to SUMO traffic light"""
        # SUMO traffic light states (for our 4-way junction):
        # 'r' = red, 'g' = green, 'y' = yellow
        # Order: NS, NS, EW, EW (depends on network)
        
        # Get current TL program
        programs = traci.trafficlight.getAllProgramLogics(TL_ID)
        if not programs:
            return
        
        # Define phase strings (varies by network - SUMO auto-generates)
        # For our 4-way: 8 signals total (2 lanes × 4 directions)
        phase_strings = {
            0: "GGGgrrrrGGGgrrrr",  # NS green
            1: "yyyyrrrryyyyrrrr",  # NS yellow
            2: "rrrrGGGgrrrrGGGg",  # EW green
            3: "rrrryyyyrrrryyyy",  # EW yellow
        }
        
        # Use SUMO's built-in phase
        try:
            traci.trafficlight.setPhase(TL_ID, phase)
        except:
            # Fallback: set state string directly
            if phase in phase_strings:
                num_signals = len(traci.trafficlight.getRedYellowGreenState(TL_ID))
                state = phase_strings[phase][:num_signals]
                traci.trafficlight.setRedYellowGreenState(TL_ID, state)
    
    def send_to_backend(self, counts, phase, time_in_phase):
        """Send simulation data to backend"""
        if not SEND_TO_BACKEND:
            return
        
        phase_names = ["NS_GREEN", "NS_YELLOW", "EW_GREEN", "EW_YELLOW"]
        signal_state = "GREEN" if phase in [0, 2] else "YELLOW"
        
        payload = {
            "total_vehicles_now": counts["total"],
            "total_unique_seen": self.stats["total_vehicles_served"],
            "lanes": {
                "north": {
                    "current": counts.get("north", 0),
                    "cumulative": 0,
                    "direction": "incoming",
                    "breakdown": {}
                },
                "south": {
                    "current": counts.get("south", 0),
                    "cumulative": 0,
                    "direction": "incoming",
                    "breakdown": {}
                },
                "east": {
                    "current": counts.get("east", 0),
                    "cumulative": 0,
                    "direction": "incoming",
                    "breakdown": {}
                },
                "west": {
                    "current": counts.get("west", 0),
                    "cumulative": 0,
                    "direction": "incoming",
                    "breakdown": {}
                }
            }
        }
        
        try:
            requests.post(
                f"{BACKEND_URL}/traffic/{INTERSECTION_ID}/detailed",
                json=payload,
                timeout=0.5
            )
        except:
            pass  # Don't crash sim if backend down
    
    def get_metrics(self):
        """Calculate performance metrics"""
        # Average waiting time of all vehicles
        wait_times = []
        for veh_id in traci.vehicle.getIDList():
            wait_times.append(traci.vehicle.getWaitingTime(veh_id))
        
        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
        
        # Total CO2 emissions
        # pyrefly: ignore [no-matching-overload]
        total_co2 = sum(traci.vehicle.getCO2Emission(v) for v in traci.vehicle.getIDList())
        
        # Vehicles arrived (completed trip)
        arrived = traci.simulation.getArrivedNumber()
        # pyrefly: ignore [unsupported-operation]
        self.stats["total_vehicles_served"] += arrived
        
        return {
            "avg_wait_time": round(avg_wait, 2),
            "total_co2_mg": round(total_co2, 2),
            "vehicles_arrived": self.stats["total_vehicles_served"],
            "vehicles_in_sim": len(traci.vehicle.getIDList())
        }


def run_simulation():
    """Main simulation loop"""
    # Start SUMO with TraCI
    sumo_cmd = [SUMO_BINARY, "-c", CONFIG_FILE, "--no-warnings", "--quit-on-end"]
    traci.start(sumo_cmd)
    
    controller = AdaptiveSignalController()
    
    print("🚦 SMART_ROUTE Adaptive Controller Started")
    print(f"📡 Backend: {BACKEND_URL}")
    print("Press Ctrl+C to stop\n")
    
    step = 0
    last_backend_send = 0
    last_metrics_print = 0
    
    try:
        # pyrefly: ignore [unsupported-operation]
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            current_time = traci.simulation.getTime()
            
            # Get vehicle counts
            counts = controller.get_vehicle_counts()
            
            # Decide signal phase
            new_phase = controller.decide_phase(counts, current_time)
            controller.apply_phase(new_phase)
            
            # Send to backend every 2 seconds
            # pyrefly: ignore [unsupported-operation]
            if current_time - last_backend_send >= 2:
                # pyrefly: ignore [unsupported-operation]
                time_in_phase = current_time - controller.phase_start_time
                controller.send_to_backend(counts, new_phase, time_in_phase)
                last_backend_send = current_time
            
            # Print metrics every 10 seconds
            # pyrefly: ignore [unsupported-operation]
            if current_time - last_metrics_print >= 10:
                metrics = controller.get_metrics()
                phase_name = ["NS-GREEN", "NS-YELLOW", "EW-GREEN", "EW-YELLOW"][new_phase]
                # pyrefly: ignore [bad-argument-type]
                print(f"⏱  T={int(current_time)}s | Phase={phase_name} | "
                      f"NS={counts['ns_total']} EW={counts['ew_total']} | "
                      f"Wait={metrics['avg_wait_time']}s | "
                      f"Arrived={metrics['vehicles_arrived']}")
                last_metrics_print = current_time
            
            step += 1
    
    except KeyboardInterrupt:
        print("\n⏹  Simulation stopped by user")
    
    finally:
        # Print final stats
        metrics = controller.get_metrics()
        print("\n" + "="*50)
        print("📊 FINAL RESULTS (Adaptive Controller)")
        print("="*50)
        print(f"Total vehicles served: {metrics['vehicles_arrived']}")
        print(f"Average wait time: {metrics['avg_wait_time']}s")
        print(f"Total CO2 emissions: {metrics['total_co2_mg']/1000:.2f} g")
        print(f"Phase changes: {controller.stats['decisions_made']}")
        print("="*50)
        
        traci.close()


if __name__ == "__main__":
    run_simulation()