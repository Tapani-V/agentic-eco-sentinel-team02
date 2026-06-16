# Week 2 Day 1-4: Step-by-Step Implementation

**Format:** You complete each step, then I brief you on the next step and provide code when requested.

---

## Architecture Summary (Updated)

**Two Separate S3 Buckets:**

1. **MCP Tools Bucket** (Phase 1 now)
   - Name: `agentic-ai-poc-3-1-mcp-tools`
   - Contains: `mcp/spare_parts_inventory.json` (only MCP tools data)
   - Access: Lambda/ECS functions read from here
   - Setup: You'll do this in Step 1

2. **Sensor Data Bucket** (Phase 2+)
   - Name: `agentic-ai-poc-3-1-sensor-data`
   - Contains: `devices/device-*.json`, `motor-*.json`, etc.
   - Access: Agents will read from here when they move to AWS
   - Setup: Later (agents stay local for Phase 1)

**Local Data (Phase 1):**
- Agents still read from: `data/generated/` locally
- No upload to sensor bucket yet
- Will upload to sensor bucket in Phase 2

---

## Step 1: Generate Data Locally

**Objective:** Create the JSON data files that MCP tools will use (spare parts inventory).

**What to do:**
1. Generate spare parts inventory file
2. Verify it was created
3. Check the file content briefly

**When done:** Tell me "Step 1 complete" and I'll brief you on Step 2.

---

## Running Commands

**Step 1 Command:**
```bash
python -m src.data.inventory_data_generator --output-dir data/generated
```

**Verify:**
```bash
ls -lh data/generated/spare_parts_inventory.json
cat data/generated/spare_parts_inventory.json | head -50
```
