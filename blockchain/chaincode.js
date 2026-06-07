/**
 * SmartRoute — Chaincode Interface
 * ==================================
 * Defines the smart-contract logic that runs on the ledger.
 * Functions mirror Hyperledger Fabric chaincode conventions so
 * this can be deployed directly to a Fabric network later.
 *
 * Each function is also callable from bridge.js via direct import.
 */

'use strict';

import crypto from 'crypto';

// ── Data Schemas ─────────────────────────────────────────────────

/**
 * @typedef {Object} SignalEvent
 * @property {string} intersection_id
 * @property {string} signal           - 'RED' | 'YELLOW' | 'GREEN'
 * @property {number} vehicle_count
 * @property {string} algorithm        - 'webster' | 'fixed' | 'manual'
 * @property {number} [green_ns]       - NS green seconds (adaptive only)
 * @property {number} [green_ew]       - EW green seconds (adaptive only)
 * @property {string} timestamp
 * @property {string} event_id         - SHA-256 of content
 */

// ── Core Chaincode Functions ─────────────────────────────────────

/**
 * logSignalChange — called by the adaptive controller every time
 * the signal or green split changes.
 *
 * @param {Object} ctx   - stub context (Fabric) or plain object
 * @param {SignalEvent} event
 * @returns {SignalEvent} The committed event with its ID
 */
export function logSignalChange(ctx, event) {
  const record = {
    ...event,
    timestamp: event.timestamp ?? new Date().toISOString(),
  };

  // Deterministic event ID from content (makes records idempotent)
  record.event_id = crypto
    .createHash('sha256')
    .update(JSON.stringify({ ...record, event_id: undefined }))
    .digest('hex');

  // Fabric stub: ctx.stub.putState(record.event_id, Buffer.from(JSON.stringify(record)))
  // For local mode: bridge.js handles persistence

  return record;
}

/**
 * getIntersectionHistory — query all events for an intersection.
 *
 * @param {Object} ctx
 * @param {string} intersection_id
 * @returns {SignalEvent[]}
 */
export function getIntersectionHistory(ctx, intersection_id) {
  // Fabric: use ctx.stub.getStateByRange / rich query with CouchDB
  // For local mode: bridge.js queries its LevelDB ledger
  return [];
}

/**
 * verifyEvent — confirm an event has not been tampered with.
 *
 * @param {SignalEvent} event  - event as stored on ledger
 * @returns {{ valid: boolean, reason: string }}
 */
export function verifyEvent(event) {
  const { event_id, ...rest } = event;
  const computed = crypto
    .createHash('sha256')
    .update(JSON.stringify(rest))
    .digest('hex');

  const valid = computed === event_id;
  return {
    valid,
    reason: valid
      ? 'Event integrity verified ✓'
      : `TAMPER DETECTED — expected ${event_id}, got ${computed}`,
  };
}

/**
 * summariseIntersection — aggregate stats from a list of events.
 *
 * @param {SignalEvent[]} events
 * @returns {Object} Summary stats
 */
export function summariseIntersection(events) {
  if (!events.length) return { total: 0 };

  const signals      = { RED: 0, YELLOW: 0, GREEN: 0 };
  const algorithms   = {};
  let totalVehicles  = 0;
  let totalGreenNS   = 0;
  let totalGreenEW   = 0;
  let countGreen     = 0;

  for (const e of events) {
    signals[e.signal]             = (signals[e.signal]       ?? 0) + 1;
    algorithms[e.algorithm]       = (algorithms[e.algorithm] ?? 0) + 1;
    totalVehicles                += e.vehicle_count ?? 0;

    if (e.green_ns !== undefined) { totalGreenNS += e.green_ns; countGreen++; }
    if (e.green_ew !== undefined)   totalGreenEW += e.green_ew;
  }

  return {
    total              : events.length,
    first_event        : events[0].timestamp,
    last_event         : events[events.length - 1].timestamp,
    signal_distribution: signals,
    algorithm_usage    : algorithms,
    avg_vehicles       : +(totalVehicles  / events.length).toFixed(2),
    avg_green_ns       : countGreen ? +(totalGreenNS / countGreen).toFixed(1) : null,
    avg_green_ew       : countGreen ? +(totalGreenEW / countGreen).toFixed(1) : null,
  };
}

// ── Fabric Bootstrap (no-op for local mode) ──────────────────────
export const chaincode = {
  logSignalChange,
  getIntersectionHistory,
  verifyEvent,
  summariseIntersection,
};

export default chaincode;
