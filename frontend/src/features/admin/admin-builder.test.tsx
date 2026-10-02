import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

import { AdminChallengeList } from "./challenge-list";
import { ChallengeEditor } from "./challenge-editor";
import { GraderEditor } from "./grader-editor";
import { emptyChallenge } from "./types";

describe("admin challenge builder", () => {
  it("renders challenge metadata and edit actions", () => {
    const markup = renderToStaticMarkup(
      <AdminChallengeList
        challenges={[{
          slug: "exact-output",
          title: "Exact Output",
          track: "control",
          difficulty: "easy",
          order: 1,
          version: "1",
          current_version: "1",
          publication_state: "published",
          visible_test_count: 3,
          hidden_test_count: 6,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }]}
      />,
    );
    expect(markup).toContain("Exact Output");
    expect(markup).toContain("3 visible");
    expect(markup).toContain("6 hidden");
    expect(markup).toContain("/admin/challenges/exact-output");
  });

  it("renders grader-specific controls", () => {
    const labels = renderToStaticMarkup(
      <GraderEditor value={{ type: "allowed_label", allowed_labels: ["YES", "NO"] }} onChange={() => undefined} />,
    );
    const schema = renderToStaticMarkup(
      <GraderEditor value={{ type: "json_schema", schema: { type: "object" } }} onChange={() => undefined} />,
    );
    expect(labels).toContain("Allowed labels");
    expect(labels).toContain("YES, NO");
    expect(schema).toContain("JSON schema");
  });

  it("visually separates visible and server-only hidden tests", () => {
    const challenge = emptyChallenge();
    challenge.title = "Draft challenge";
    challenge.slug = "draft-challenge";
    challenge.hidden_test_cases = [{ id: "hidden-1", input: "secret", expected_output: "YES", grader: { type: "exact_match" } }];
    const markup = renderToStaticMarkup(<ChallengeEditor initial={challenge} />);
    expect(markup).toContain("Visible tests");
    expect(markup).toContain("Hidden tests");
    expect(markup).toContain("SERVER-ONLY");
    expect(markup).toContain("Save draft");
    expect(markup).toContain("NO SIDE EFFECTS");
  });
});
