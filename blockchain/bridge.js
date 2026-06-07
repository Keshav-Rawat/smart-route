/**
 * SmartRoute — Blockchain Audit Bridge
 * ======================================
 * Logs every traffic signal change to an immutable audit trail.
 * Uses an in-process LevelDB ledger (lightweight, no Fabric needed)
 * that mimics Hyperledger Fabric's key-value chaincode interface.
 *
 * For production: swap the LevelDB stub with a real Fabric SDK gateway.
 *
 * Usage:
 *   node bridge.js
 *   # Starts HTTP server on :3001
 *
 * Endpoints:
 *   POST /log              { intersection_id, signal, vehicle_count, algorithm }
 *   GET  /audit/:id        → full history for intersection
 *   GET  /audit/:id/latest → most recent entry
 *   GET  /verify/:hash     → verify a record by hash
 *   GET  /stats            → chain statistics
 */

import express from 'express';
import crypto  from 'crypto';
import { fileURLToPath } from 'url';
import path    from 'path';
import fs      from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT      = process.env.BRIDGE_PORT || 3001;

// ── Lightweight File-Based Ledger ────────────────────────────────
// In production, replace with @hyperledger/fabric-gateway
const LEDGER_FILE = path.join(__dirname, 'ledger.json');

function loadLedger() {
  try {
    return JSON.parse(fs.readFileSync(LEDGER_FILE, 'utf8'));
  } catch {
    return { blocks: [], index: {} };
  }
}

function saveLedger(ledger) {
  fs.writeFileSync(LEDGER_FILE, JSON.stringify(ledger, null, 2));
}

// ── Hashing ──────────────────────────────────────────────────────
function sha256(data) {
  return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
}

function createBlock(prevHash, record) {
  const block = {
    index:     0,           // filled in below
    timestamp: new Date().toISOString(),
    prevHash,
    record,
    nonce:     Math.random().toString(36).slice(2),
  };
  block.hash = sha256(block);
  return block;
}

// ── REST API ─────────────────────────────────────────────────────
const app = express();
app.use(express.json());

// CORS
app.use((_, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  next();
});

app.get('/health', (_, res) => {
  const ledger = loadLedger();
  res.json({
    status:      'healthy',
    chain_length: ledger.blocks.length,
    timestamp:   new Date().toISOString(),
  });
});

/**
 * POST /log
 * Body: { intersection_id, signal, vehicle_count, algorithm, green_ns?, green_ew? }
 * Appends a new tamper-evident block to the chain.
 */
app.post('/log', (req, res) => {
  const { intersection_id, signal, vehicle_count, algorithm, green_ns, green_ew } = req.body;

  if (!intersection_id || !signal) {
    return res.status(400).json({ error: 'intersection_id and signal are required' });
  }

  const ledger   = loadLedger();
  const prevHash = ledger.blocks.length > 0
    ? ledger.blocks[ledger.blocks.length - 1].hash
    : '0'.repeat(64);

  const record = {
    intersection_id,
    signal,
    vehicle_count : Number(vehicle_count ?? 0),
    algorithm     : algorithm ?? 'unknown',
    ...(green_ns !== undefined && { green_ns: Number(green_ns) }),
    ...(green_ew !== undefined && { green_ew: Number(green_ew) }),
  };

  const block = createBlock(prevHash, record);
  block.index  = ledger.blocks.length;

  ledger.blocks.push(block);

  // Index by intersection_id for fast queries
  if (!ledger.index[intersection_id]) ledger.index[intersection_id] = [];
  ledger.index[intersection_id].push(block.index);

  saveLedger(ledger);

  console.log(`[Block ${block.index}] ${intersection_id} → ${signal} | ${vehicle_count} veh | ${algorithm}`);

  res.status(201).json({
    success  : true,
    block_index: block.index,
    hash     : block.hash,
    timestamp: block.timestamp,
  });
});

/**
 * GET /audit/:intersection_id
 * Returns the full immutable audit trail for an intersection.
 */
app.get('/audit/:id', (req, res) => {
  const ledger  = loadLedger();
  const indices = ledger.index[req.params.id] ?? [];
  const history = indices.map(i => ledger.blocks[i]);

  res.json({
    intersection_id: req.params.id,
    total_records  : history.length,
    history,
  });
});

/**
 * GET /audit/:intersection_id/latest
 */
app.get('/audit/:id/latest', (req, res) => {
  const ledger  = loadLedger();
  const indices = ledger.index[req.params.id] ?? [];
  if (indices.length === 0) return res.status(404).json({ error: 'No records found' });

  const latest = ledger.blocks[indices[indices.length - 1]];
  res.json(latest);
});

/**
 * GET /verify/:hash
 * Verifies a block has not been tampered with.
 */
app.get('/verify/:hash', (req, res) => {
  const ledger = loadLedger();
  const block  = ledger.blocks.find(b => b.hash === req.params.hash);

  if (!block) return res.status(404).json({ valid: false, error: 'Hash not found' });

  // Recompute hash (excluding hash field itself)
  const { hash: storedHash, ...rest } = block;
  const computed = sha256(rest);
  const valid    = computed === storedHash;

  res.json({
    valid,
    block_index: block.index,
    stored_hash: storedHash,
    computed_hash: computed,
    message: valid ? 'Block integrity verified ✓' : 'TAMPER DETECTED ✗',
  });
});

/**
 * GET /stats
 */
app.get('/stats', (_, res) => {
  const ledger = loadLedger();
  const intersections = Object.keys(ledger.index);

  const signals = { RED: 0, YELLOW: 0, GREEN: 0 };
  ledger.blocks.forEach(b => {
    if (b.record?.signal) signals[b.record.signal] = (signals[b.record.signal] ?? 0) + 1;
  });

  res.json({
    chain_length       : ledger.blocks.length,
    intersections_tracked: intersections.length,
    intersections,
    signal_distribution: signals,
    genesis_time : ledger.blocks[0]?.timestamp ?? null,
    latest_time  : ledger.blocks[ledger.blocks.length - 1]?.timestamp ?? null,
  });
});

app.listen(PORT, () => {
  console.log(`\n🔗 SmartRoute Blockchain Bridge`);
  console.log(`   Audit ledger : ${LEDGER_FILE}`);
  console.log(`   API          : http://localhost:${PORT}`);
  console.log(`   POST /log to record a signal event\n`);
});
