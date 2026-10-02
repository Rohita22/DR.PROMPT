import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ApplicationRunResponse, ApplicationSubmitResponse } from "@/lib/api/challenges";

import { ApplicationRunResults, ApplicationSubmitResults, StarterPreview } from "./application-results";

const shot = (viewport: string) => ({
  viewport,
  width: viewport === "desktop" ? 1280 : 390,
  height: 800,
  image: `data:image/png;base64,${viewport}`,
});

const run: ApplicationRunResponse = {
  challenge_type: "application",
  challenge: "responsive-hero",
  challenge_id: "control-responsive-hero",
  version: "1",
  passed: 3,
  total: 4,
  evaluation_score: 75,
  agent: { status: "applied", message: null },
  changed_files: [{ path: "src/styles.css", additions: 21, deletions: 2 }],
  build: { status: "passed", log: "Built dist/index.html and dist/styles.css." },
  checks: [
    { id: "build", label: "Project builds", passed: true, message: null },
    {
      id: "mobile_no_overflow",
      label: "No horizontal overflow at 390px",
      passed: false,
      message: "At 390px the page scrolls horizontally.",
    },
  ],
  screenshots: [shot("desktop"), shot("mobile")],
};

describe("application challenge views", () => {
  it("shows the starter next to the AI result with visible checks, build, and changes", () => {
    const markup = renderToStaticMarkup(<ApplicationRunResults result={run} starterSrc="/starter.png" />);

    expect(markup).toContain("This is what your instructions made the AI build.");
    expect(markup).toContain("STARTER");
    expect(markup).toContain("YOUR AI’S RESULT");
    expect(markup).toContain('src="/starter.png"');
    expect(markup).toContain("data:image/png;base64,desktop");
    expect(markup).toContain("data:image/png;base64,mobile");
    expect(markup).toContain("At 390px the page scrolls horizontally.");
    expect(markup).toContain("src/styles.css");
    expect(markup).toContain("+21");
    expect(markup).toContain("Built dist/index.html");
  });

  it("explains a rejected edit set without rendering a result screenshot", () => {
    const markup = renderToStaticMarkup(
      <ApplicationRunResults
        result={{
          ...run,
          passed: 0,
          evaluation_score: 0,
          agent: { status: "rejected", message: "The coding agent tried to edit a protected file: build.mjs." },
          changed_files: [],
          build: { status: "skipped", log: "" },
          screenshots: [],
        }}
        starterSrc="/starter.png"
      />,
    );

    expect(markup).toContain("protected file: build.mjs");
    expect(markup).toContain("Nothing was built because the agent’s edits were rejected.");
    expect(markup).toContain("No files changed.");
    expect(markup).not.toContain("data:image/png");
  });

  it("renders aggregate hidden results with evaluation terminology and no check details", () => {
    const submit: ApplicationSubmitResponse = {
      challenge_type: "application",
      challenge: "responsive-hero",
      version: "1",
      passed: 8,
      total: 9,
      evaluation_score: 88.89,
      prompt_tokens: 120,
      efficiency: 90,
      score: 89.11,
      stars: 2,
      xp_earned: 125,
      total_xp: 900,
      best_score: 89.11,
      best_stars: 2,
      completed: true,
      agent_status: "applied",
      screenshot: shot("desktop"),
    };
    const markup = renderToStaticMarkup(<ApplicationSubmitResults result={submit} />);

    expect(markup).toContain("Hidden checks");
    expect(markup).toContain("8 / 9");
    expect(markup).toContain("Evaluation");
    expect(markup).toContain("88.89%");
    expect(markup).not.toContain("Accuracy");
    expect(markup).toContain("SUBMITTED RESULT");
    expect(markup).not.toContain("FAIL");
  });

  it("shows the starter reference and the editable files in the brief", () => {
    const markup = renderToStaticMarkup(
      <StarterPreview src="/starter.png" files={["src/index.html", "src/styles.css"]} />,
    );
    expect(markup).toContain("STARTER APP");
    expect(markup).toContain("src/index.html");
    expect(markup).toContain("src/styles.css");
  });
});

it("renders Pricing Grid with three arbitrary screenshot labels", () => {
  const result = { ...run, challenge: "pricing-grid", screenshots: [
    { ...shot("wide"), label: "Wide workspace", width: 1440 },
    { ...shot("tablet"), label: "Tablet landscape", width: 900 },
    { ...shot("compact"), label: "Compact view", width: 320 },
  ] };
  const html = renderToStaticMarkup(<ApplicationRunResults result={result} />);
  expect(html).toContain("Wide workspace"); expect(html).toContain("Tablet landscape");
  expect(html).toContain("Compact view"); expect(html).toContain("data:image/png;base64,compact");
  expect(html).not.toContain("hero"); expect(html).not.toContain("1280px desktop");
});

it.each(["Responsive Hero", "Pricing Grid"])("uses challenge metadata in the %s starter brief", (title) => {
  const html = renderToStaticMarkup(<StarterPreview title={title} label="Phone" src="/starter.png" files={["src/styles.css"]} />);
  expect(html).toContain(`${title} starter`); expect(html).toContain("Phone");
  expect(html).not.toContain("stacked hero section");
});
