"""
n8n workflow JSON generator for reconciliation workflows.
Generates JavaScript Code nodes only.
"""
import json
import uuid
from typing import Dict, Any, List


class N8nWorkflowExporter:
    """Generates n8n-compatible workflow JSON files with JavaScript nodes."""

    def generate_workflow(
        self,
        python_code: str,
        workflow_name: str = "Reconciliation Workflow"
    ) -> Dict[str, Any]:
        """
        Generate n8n workflow JSON with JavaScript Code node.

        Args:
            python_code: The generated reconciliation Python code (used as reference)
            workflow_name: Name for the workflow

        Returns:
            n8n workflow JSON structure
        """
        workflow_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        nodes = []

        # Node 1: Manual Trigger
        trigger_node = self._create_trigger_node()
        nodes.append(trigger_node)

        # Node 2: Read/Set Data (placeholder for data input)
        read_data_node = self._create_read_data_node()
        nodes.append(read_data_node)

        # Node 3: JavaScript Code Node
        js_node = self._create_js_code_node(python_code)
        nodes.append(js_node)

        # Node 4: Output/Results node
        output_node = self._create_output_node()
        nodes.append(output_node)

        # Build connections
        connections = self._build_connections(nodes)

        return {
            "name": workflow_name,
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": {
                "executionOrder": "v1"
            },
            "versionId": version_id,
            "meta": {
                "instanceId": "recon-agent-generated",
                "templateCredsSetupCompleted": True
            },
            "id": workflow_id,
            "tags": [
                {"name": "reconciliation"},
                {"name": "auto-generated"}
            ],
            "pinData": {}
        }

    def _create_trigger_node(self) -> Dict[str, Any]:
        """Create form trigger node with file upload fields."""
        return {
            "id": str(uuid.uuid4()),
            "name": "Upload Files",
            "type": "n8n-nodes-base.formTrigger",
            "typeVersion": 2.2,
            "position": [0, 300],
            "webhookId": str(uuid.uuid4()),
            "parameters": {
                "formTitle": "Reconciliation Data Upload",
                "formDescription": "Upload your two datasets (CSV or PDF) for reconciliation",
                "formFields": {
                    "values": [
                        {
                            "fieldLabel": "Dataset A (Source)",
                            "fieldType": "file",
                            "requiredField": True,
                            "acceptFileTypes": ".csv,.pdf,.xlsx,.xls",
                            "multipleFiles": False
                        },
                        {
                            "fieldLabel": "Dataset B (Target)",
                            "fieldType": "file",
                            "requiredField": True,
                            "acceptFileTypes": ".csv,.pdf,.xlsx,.xls",
                            "multipleFiles": False
                        },
                        {
                            "fieldLabel": "Matching Hint (Optional)",
                            "fieldType": "textarea",
                            "requiredField": False,
                            "placeholder": "e.g., Match by RFX or MY reference numbers"
                        }
                    ]
                },
                "options": {
                    "respondWithOptions": {
                        "values": {
                            "formSubmittedText": "Files uploaded successfully! Processing reconciliation..."
                        }
                    }
                }
            }
        }

    def _create_read_data_node(self) -> Dict[str, Any]:
        """Create node for parsing uploaded files from form."""
        return {
            "id": str(uuid.uuid4()),
            "name": "Parse Uploaded Files",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [220, 300],
            "parameters": {
                "jsCode": self._generate_file_parser_code(),
                "mode": "runOnceForAllItems"
            },
            "notesInFlow": True,
            "notes": "Parses uploaded CSV files from the form. For PDF files, you may need to add an Extract from PDF node before this."
        }

    def _generate_file_parser_code(self) -> str:
        """Generate JavaScript code for parsing uploaded CSV files."""
        return '''// ============================================
// Parse Uploaded Files from Form
// ============================================

const items = $input.all();
const formData = items[0]?.json || {};

// Get binary data from form uploads
const binaryData = items[0]?.binary || {};

// Helper function to parse CSV content
function parseCSV(csvContent) {
  const lines = csvContent.trim().split('\\n');
  if (lines.length === 0) return [];

  // Parse header
  const header = parseCSVLine(lines[0]);

  // Parse data rows
  const data = [];
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim()) {
      const values = parseCSVLine(lines[i]);
      const row = {};
      header.forEach((col, idx) => {
        row[col.trim()] = values[idx]?.trim() || '';
      });
      data.push(row);
    }
  }
  return data;
}

// Helper to parse a single CSV line (handles quoted fields)
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current);
  return result;
}

// Parse Dataset A
let datasetA = [];
const fileAKey = Object.keys(binaryData).find(k => k.includes('Dataset_A') || k.includes('file') || k === 'data');
if (fileAKey && binaryData[fileAKey]) {
  const fileA = binaryData[fileAKey];
  if (fileA.mimeType?.includes('csv') || fileA.fileName?.endsWith('.csv')) {
    const content = Buffer.from(fileA.data, 'base64').toString('utf-8');
    datasetA = parseCSV(content);
  }
}

// Parse Dataset B
let datasetB = [];
const fileBKey = Object.keys(binaryData).find(k => k.includes('Dataset_B') || k.includes('file1') || k === 'data1');
if (fileBKey && binaryData[fileBKey]) {
  const fileB = binaryData[fileBKey];
  if (fileB.mimeType?.includes('csv') || fileB.fileName?.endsWith('.csv')) {
    const content = Buffer.from(fileB.data, 'base64').toString('utf-8');
    datasetB = parseCSV(content);
  }
}

// Get optional hint from form
const hint = formData['Matching Hint (Optional)'] || formData.hint || '';

// Return parsed data for next node
return [{
  json: {
    dataset_a: datasetA,
    dataset_b: datasetB,
    hint: hint,
    file_a_rows: datasetA.length,
    file_b_rows: datasetB.length
  }
}];
'''

    def _create_js_code_node(self, python_code: str) -> Dict[str, Any]:
        """Create JavaScript Code node with reconciliation logic."""
        js_code = self._generate_js_code(python_code)

        return {
            "id": str(uuid.uuid4()),
            "name": "Reconciliation Logic",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
            "parameters": {
                "jsCode": js_code,
                "mode": "runOnceForAllItems"
            },
            "notesInFlow": True,
            "notes": "JavaScript reconciliation logic. Modify this code to match your specific data structure and matching requirements."
        }

    def _create_output_node(self) -> Dict[str, Any]:
        """Create output/results node."""
        return {
            "id": str(uuid.uuid4()),
            "name": "Reconciliation Results",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [660, 300],
            "parameters": {
                "mode": "manual",
                "duplicateItem": False,
                "assignments": {
                    "assignments": [
                        {
                            "id": str(uuid.uuid4()),
                            "name": "matched_count",
                            "value": "={{ $json.matched?.length || $json.matched_count || 0 }}",
                            "type": "number"
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "name": "unmatched_a_count",
                            "value": "={{ $json.unmatched_a?.length || 0 }}",
                            "type": "number"
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "name": "unmatched_b_count",
                            "value": "={{ $json.unmatched_b?.length || 0 }}",
                            "type": "number"
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "name": "matched",
                            "value": "={{ $json.matched }}",
                            "type": "array"
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "name": "unmatched_a",
                            "value": "={{ $json.unmatched_a }}",
                            "type": "array"
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "name": "unmatched_b",
                            "value": "={{ $json.unmatched_b }}",
                            "type": "array"
                        }
                    ]
                },
                "options": {}
            }
        }

    def _build_connections(self, nodes: List[Dict]) -> Dict[str, Any]:
        """Build connections between nodes."""
        connections = {}

        # Trigger -> Read Data
        connections[nodes[0]["name"]] = {
            "main": [[{"node": nodes[1]["name"], "type": "main", "index": 0}]]
        }

        # Read Data -> JS Code
        connections[nodes[1]["name"]] = {
            "main": [[{"node": nodes[2]["name"], "type": "main", "index": 0}]]
        }

        # JS Code -> Output
        connections[nodes[2]["name"]] = {
            "main": [[{"node": nodes[3]["name"], "type": "main", "index": 0}]]
        }

        return connections

    def _generate_js_code(self, python_code: str) -> str:
        """Generate JavaScript code for n8n Code node."""
        # Clean python code for reference comment
        clean_python = self._clean_code(python_code)

        return f'''// ============================================
// Reconciliation Workflow (Auto-generated)
// ============================================
//
// Original Python logic for reference:
/*
{clean_python}
*/

// Get input data from previous node (parsed from form uploads)
const items = $input.all();
const inputData = items[0]?.json || {{}};

// Extract datasets from parsed form data
const datasetA = inputData.dataset_a || [];
const datasetB = inputData.dataset_b || [];
const userHint = inputData.hint || '';

// Log dataset info
console.log(`Dataset A: ${{datasetA.length}} records`);
console.log(`Dataset B: ${{datasetB.length}} records`);
if (userHint) console.log(`User hint: ${{userHint}}`);

// ============================================
// RECONCILIATION LOGIC
// ============================================

const matched = [];
const unmatchedA = [...datasetA];
const unmatchedB = [...datasetB];

// Helper function to extract reference numbers (RFX or MY patterns)
function extractReference(text) {{
  if (!text) return null;
  const match = String(text).match(/(RFX[A-Z0-9]+|MY\\s*[A-Z0-9]+)/i);
  return match ? match[1].replace(/\\s+/g, '').toUpperCase() : null;
}}

// Helper function to normalize text for matching
function normalize(text) {{
  if (!text) return '';
  return String(text).trim().toUpperCase().replace(/\\s+/g, ' ');
}}

// Process each record in Dataset A
datasetA.forEach((recordA) => {{
  // Extract reference from Narration field (adjust field name as needed)
  const narration = recordA.Narration || recordA.narration || recordA.Description || recordA.description || '';
  const refA = extractReference(narration);

  if (refA) {{
    // Find matching record in Dataset B by reference
    const matchIndex = unmatchedB.findIndex(recordB => {{
      const descB = recordB.Description || recordB.description || recordB.Narration || recordB.narration || '';
      const refB = extractReference(descB);

      // Match if reference is found in description or exact match
      return refB === refA || String(descB).toUpperCase().includes(refA);
    }});

    if (matchIndex !== -1) {{
      // Found a match
      const matchedRecordB = unmatchedB[matchIndex];

      matched.push({{
        // Fields from Dataset A
        ...recordA,
        // Add matched record from B
        matched_from_b: matchedRecordB,
        // Matching info
        match_key: refA,
        match_type: 'reference'
      }});

      // Remove from unmatched lists
      unmatchedB.splice(matchIndex, 1);
      const aIndex = unmatchedA.findIndex(r =>
        JSON.stringify(r) === JSON.stringify(recordA)
      );
      if (aIndex !== -1) unmatchedA.splice(aIndex, 1);
    }}
  }}
}});

// Calculate statistics
const totalA = datasetA.length;
const totalB = datasetB.length;
const matchedCount = matched.length;
const matchRate = totalA > 0 ? (matchedCount / totalA) : 0;

// ============================================
// OUTPUT
// ============================================
return [{{
  json: {{
    matched: matched,
    unmatched_a: unmatchedA,
    unmatched_b: unmatchedB,
    statistics: {{
      matched_count: matchedCount,
      unmatched_a_count: unmatchedA.length,
      unmatched_b_count: unmatchedB.length,
      total_a: totalA,
      total_b: totalB,
      match_rate: (matchRate * 100).toFixed(2) + '%'
    }}
  }}
}}];
'''

    def _clean_code(self, code: str) -> str:
        """Remove markdown code blocks and clean up."""
        if "```python" in code:
            parts = code.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) > 1:
                code = parts[1].split("```")[0] if len(parts) > 2 else parts[1]

        return code.strip()

    def export_to_json(self, workflow: Dict[str, Any], indent: int = 2) -> str:
        """Export workflow as formatted JSON string."""
        return json.dumps(workflow, indent=indent)


# Global exporter instance
n8n_exporter = N8nWorkflowExporter()
