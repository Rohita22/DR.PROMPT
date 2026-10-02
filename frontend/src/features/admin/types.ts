import type { ApplicationDefinition, ApplicationTestData } from "./application-types";
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type GraderConfig =
  | { type: "exact_match" }
  | { type: "case_insensitive_exact_match" }
  | { type: "allowed_label"; allowed_labels: string[] }
  | { type: "json_schema"; schema: { [key: string]: JsonValue } }
  | { type: "field_comparison"; fields: string[] }
  | { type: "array_comparison"; order_matters: boolean };

export type AuthoringTest = {
  id: string;
  input: JsonValue;
  expected_output: JsonValue;
  grader: GraderConfig;
};

export type ChallengeDefinition = {
  challenge_type: "text" | "application";
  application: ApplicationDefinition | null;
  id?: string;
  slug: string;
  track: "control" | "extract" | "classify" | "structure";
  order: number;
  current_version?: string | null;
  version: string;
  title: string;
  description: string;
  objective: string;
  constraints: string[];
  difficulty: "easy" | "medium" | "hard" | "boss";
  visible_examples: { input: JsonValue; expected_output: JsonValue; explanation: string | null }[];
  visible_test_cases: AuthoringTest[];
  hidden_test_cases: AuthoringTest[];
  prompt_token_limit: number | null;
  default_grader: GraderConfig;
  model: {
    model_id: string;
    temperature: number;
    max_output_tokens: number;
    system_wrapper: string | null;
    configuration_version: string | null;
    reasoning_effort?: "low" | "medium" | "high" | null;
  };
  scoring: {
    accuracy_weight: number;
    efficiency_weight: number;
    efficiency_tiers: { max_tokens: number; score: number }[];
    score_above_max: number;
    one_star: number;
    two_stars: number;
    three_stars: number;
    three_star_max_prompt_tokens: number | null;
  };
  publication_state: "draft" | "published" | "retired";
  versions?: { version: string; publication_state: string; created_at: string }[];
  created_at?: string;
  updated_at?: string;
};

export type AdminChallengeSummary = {
  slug: string;
  title: string;
  track: string;
  difficulty: string;
  order: number;
  version: string;
  current_version: string | null;
  publication_state: string;
  visible_test_count: number;
  hidden_test_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminTestResult = ApplicationTestData & {
  challenge: string;
  version: string;
  prompt_tokens: number;
  passed: number;
  total: number;
  accuracy: number;
  efficiency: number;
  score: number;
  stars: number;
  visible_tests: AdminTestCaseResult[];
  hidden_tests: AdminTestCaseResult[];
};

export type AdminTestCaseResult = {
  id: string;
  input: JsonValue;
  expected: JsonValue;
  actual: JsonValue;
  passed: boolean;
  failure_reason: string | null;
};

export const emptyChallenge = (): ChallengeDefinition => ({
  challenge_type: "text",
  application: null,
  slug: "",
  track: "control",
  order: 0,
  version: "1",
  title: "",
  description: "",
  objective: "",
  constraints: [],
  difficulty: "easy",
  visible_examples: [],
  visible_test_cases: [],
  hidden_test_cases: [],
  prompt_token_limit: 300,
  default_grader: { type: "exact_match" },
  model: {
    model_id: "openai/gpt-oss-20b",
    temperature: 0,
    max_output_tokens: 16,
    system_wrapper: "Apply the player's instruction to the next user message, which contains the test input. Do not add facts that are not present in that input.",
    configuration_version: null,
  },
  scoring: {
    accuracy_weight: 0.8,
    efficiency_weight: 0.2,
    efficiency_tiers: [
      { max_tokens: 60, score: 100 },
      { max_tokens: 100, score: 90 },
      { max_tokens: 150, score: 75 },
      { max_tokens: 250, score: 60 },
    ],
    score_above_max: 40,
    one_star: 70,
    two_stars: 90,
    three_stars: 100,
    three_star_max_prompt_tokens: 60,
  },
  publication_state: "draft",
});

