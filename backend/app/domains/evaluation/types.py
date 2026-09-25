from collections.abc import Mapping

type EvaluationValue = (
    str
    | int
    | float
    | bool
    | None
    | list["EvaluationValue"]
    | tuple["EvaluationValue", ...]
    | Mapping[str, "EvaluationValue"]
)
