import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
import { ApplicationEditor } from "./application-editor";
import { applicationValidation, copyPackageDefaults, toggleSelection } from "./application-types";
import type { ApplicationPackage } from "./application-types";
import { AdminTestResults, ChallengeEditor } from "./challenge-editor";
import { emptyChallenge } from "./types";

const pkg: ApplicationPackage = {
  id: "sample-grid", display_name: "Sample Grid", description: "Three cards, one responsive layout.",
  defaults: { package_id: "sample-grid", editable_files: ["src/index.html", "src/styles.css"], visible_checks: ["row"], hidden_checks: ["content"], viewports: [{ id: "tablet", width: 800, height: 900, label: "Tablet preview", screenshot: true }], limits: { agent_timeout_seconds: 90, build_timeout_seconds: 20, browser_timeout_seconds: 20, max_file_bytes: 32000, max_files: 2, max_log_chars: 2000 } },
  visible_checks: [{ id: "row", label: "Cards form a row", implementation: "horizontal_row", viewports: ["tablet"], count: 3, min_width_ratio: .2, tolerance: 2 }],
  hidden_checks: [{ id: "content", label: "Original content", implementation: "text_preserved", viewports: ["tablet"], count: 3, min_width_ratio: 0, tolerance: 2 }],
};

describe("application authoring", () => {
  it("selects package defaults without sharing mutable authoring state", () => {
    const selected = copyPackageDefaults(pkg);
    selected.editable_files.pop(); selected.viewports[0].label = "Changed";
    expect(pkg.defaults.editable_files).toHaveLength(2);
    expect(pkg.defaults.viewports[0].label).toBe("Tablet preview");
  });
  it("selects and removes trusted checks", () => {
    expect(toggleSelection(["row"], "overflow")).toEqual(["row", "overflow"]);
    expect(toggleSelection(["row", "overflow"], "row")).toEqual(["overflow"]);
  });
  it("validates files, check selection, screenshots, and limits", () => {
    const value = copyPackageDefaults(pkg);
    expect(applicationValidation(value, [pkg])).toBeNull();
    expect(applicationValidation(null, [pkg])).toContain("Select");
    expect(applicationValidation({ ...value, editable_files: ["build.mjs"] }, [pkg])).toContain("policy");
    expect(applicationValidation({ ...value, hidden_checks: [] }, [pkg])).toContain("hidden check");
    expect(applicationValidation({ ...value, visible_checks: ["eval"] }, [pkg])).toContain("catalog");
    expect(applicationValidation({ ...value, viewports: value.viewports.map((v) => ({ ...v, screenshot: false })) }, [pkg])).toContain("screenshot");
    expect(applicationValidation({ ...value, limits: { ...value.limits, max_files: 3 } }, [pkg])).toContain("policy");
  });
  it("shows trusted choices and private treatment without a code or JSON editor", () => {
    const html = renderToStaticMarkup(<ApplicationEditor value={pkg.defaults} packages={[pkg]} onChange={() => undefined} />);
    expect(html).toContain("Sample Grid"); expect(html).toContain("Cards form a row");
    expect(html).toContain("PRIVATE · ADMIN ONLY"); expect(html).toContain("Artifact label");
    expect(html).toContain("Agent timeout (seconds)"); expect(html).not.toContain("textarea");
  });
  it("renders type-specific application editor and locks existing type", () => {
    const challenge = { ...emptyChallenge(), challenge_type: "application" as const, application: pkg.defaults };
    const html = renderToStaticMarkup(<ChallengeEditor initial={challenge} packages={[pkg]} />);
    expect(html).toContain("Application package"); expect(html).not.toContain("Visible examples");
    expect(html).not.toContain("JSON schema"); expect(html).not.toContain('value="image"');
    expect(html).toMatch(/<select disabled=""><option value="text"/);
  });
  it("renders application admin test artifacts and private check detail", () => {
    const html = renderToStaticMarkup(<AdminTestResults result={{ challenge: "sample-grid", version: "1", prompt_tokens: 30, passed: 1, total: 2, accuracy: 50, efficiency: 100, score: 60, stars: 0, visible_tests: [], hidden_tests: [], hidden_checks: [{ id: "content", label: "Original content", passed: false, message: "Content changed." }], application: { challenge_type: "application", challenge: "sample-grid", challenge_id: "sample-grid", version: "1", passed: 1, total: 1, evaluation_score: 100, agent: { status: "applied", message: null }, changed_files: [{ path: "src/styles.css", additions: 10, deletions: 0 }], build: { status: "passed", log: "Built." }, checks: [], screenshots: [{ viewport: "tablet", label: "Tablet preview", width: 800, height: 900, image: "data:image/png;base64,test" }] } }} />);
    expect(html).toContain("Tablet preview"); expect(html).toContain("Content changed.");
    expect(html).toContain("src/styles.css"); expect(html).toContain("Built.");
    expect(html).not.toContain("XP earned");
  });
});
