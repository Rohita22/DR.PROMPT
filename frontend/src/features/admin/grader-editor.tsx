"use client";

import { JsonEditor } from "./json-editor";
import type { GraderConfig } from "./types";

const graderTypes: { value: GraderConfig["type"]; label: string }[] = [
  { value: "exact_match", label: "Exact match" },
  { value: "case_insensitive_exact_match", label: "Case-insensitive exact" },
  { value: "allowed_label", label: "Allowed label" },
  { value: "json_schema", label: "JSON schema" },
  { value: "field_comparison", label: "Field comparison" },
  { value: "array_comparison", label: "Array comparison" },
];

function defaultFor(type: GraderConfig["type"]): GraderConfig {
  if (type === "allowed_label") return { type, allowed_labels: ["YES", "NO"] };
  if (type === "json_schema") return { type, schema: { type: "object" } };
  if (type === "field_comparison") return { type, fields: ["value"] };
  if (type === "array_comparison") return { type, order_matters: true };
  return { type };
}

export function GraderEditor({ value, onChange }: { value: GraderConfig; onChange: (value: GraderConfig) => void }) {
  return (
    <div className="grader-editor">
      <label className="admin-field">
        <span>Grader</span>
        <select value={value.type} onChange={(event) => onChange(defaultFor(event.target.value as GraderConfig["type"]))}>
          {graderTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </label>
      {value.type === "allowed_label" ? (
        <label className="admin-field">
          <span>Allowed labels <em>comma separated</em></span>
          <input value={value.allowed_labels.join(", ")} onChange={(event) => onChange({ ...value, allowed_labels: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} />
        </label>
      ) : null}
      {value.type === "json_schema" ? <JsonEditor label="JSON schema" value={value.schema} onChange={(schema) => onChange({ ...value, schema: typeof schema === "object" && schema !== null && !Array.isArray(schema) ? schema : {} })} /> : null}
      {value.type === "field_comparison" ? (
        <label className="admin-field">
          <span>Compared fields <em>comma separated</em></span>
          <input value={value.fields.join(", ")} onChange={(event) => onChange({ ...value, fields: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} />
        </label>
      ) : null}
      {value.type === "array_comparison" ? (
        <label className="admin-check"><input type="checkbox" checked={value.order_matters} onChange={(event) => onChange({ ...value, order_matters: event.target.checked })} /> Order matters</label>
      ) : null}
    </div>
  );
}

