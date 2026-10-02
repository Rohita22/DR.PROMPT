import type { ApplicationCheckResult, ApplicationRunResponse } from "@/lib/api/challenges";

export type ApplicationViewport = { id: string; width: number; height: number; label: string; screenshot: boolean };
export type ApplicationLimits = { agent_timeout_seconds: number; build_timeout_seconds: number; browser_timeout_seconds: number; max_file_bytes: number; max_files: number; max_log_chars: number };
export type ApplicationDefinition = { package_id: string; editable_files: string[]; visible_checks: string[]; hidden_checks: string[]; viewports: ApplicationViewport[]; limits: ApplicationLimits };
export type PackageCheck = { id: string; label: string; implementation: string; viewports: string[]; count: number; min_width_ratio: number; tolerance: number };
export type ApplicationPackage = { execution_mode?: "static" | "sandboxed_executable"; runtime_metadata?: { runtime: string; commands: string[]; network: string; cpus: number; memory_mb: number; pids: number; timeout_seconds: number; workspace_mb: number } | null; id: string; display_name: string; description: string; defaults: ApplicationDefinition; visible_checks: PackageCheck[]; hidden_checks: PackageCheck[] };
export type ApplicationTestData = { challenge_type?: "text" | "application"; application?: ApplicationRunResponse | null; hidden_checks?: ApplicationCheckResult[] };

export function copyPackageDefaults(pkg: ApplicationPackage): ApplicationDefinition {
  return structuredClone(pkg.defaults);
}

export function toggleSelection(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function applicationValidation(value: ApplicationDefinition | null | undefined, packages: ApplicationPackage[]): string | null {
  if (!value) return "Select an application package.";
  const pkg = packages.find((item) => item.id === value.package_id);
  if (!pkg) return "The selected package is unavailable. Reload the catalog.";
  if (!value.editable_files.length) return "Select at least one editable file.";
  if (value.editable_files.some((path) => !pkg.defaults.editable_files.includes(path))) return "Editable files exceed package policy.";
  if (!value.visible_checks.length || !value.hidden_checks.length) return "Select at least one visible and one hidden check.";
  if (value.visible_checks.some((id) => !pkg.defaults.visible_checks.includes(id)) || value.hidden_checks.some((id) => !pkg.defaults.hidden_checks.includes(id))) return "Select checks from the package catalog.";
  if (!value.viewports.some((view) => view.screenshot)) return "Select at least one result screenshot.";
  for (const key of Object.keys(value.limits) as (keyof ApplicationLimits)[]) {
    if (!Number.isFinite(value.limits[key]) || value.limits[key] <= 0 || value.limits[key] > pkg.defaults.limits[key]) return "Execution limits must be positive and within package policy.";
  }
  return null;
}
