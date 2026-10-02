"use client";

import { useState } from "react";

import type { JsonValue } from "./types";

export function JsonEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: JsonValue;
  onChange: (value: JsonValue) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState("");

  function commit() {
    try {
      onChange(JSON.parse(text) as JsonValue);
      setError("");
    } catch {
      setError("Enter valid JSON. Strings need double quotes.");
    }
  }

  return (
    <label className="admin-field admin-json-field">
      <span>{label}</span>
      <textarea value={text} onChange={(event) => setText(event.target.value)} onBlur={commit} />
      {error ? <small className="field-error">{error}</small> : null}
    </label>
  );
}
