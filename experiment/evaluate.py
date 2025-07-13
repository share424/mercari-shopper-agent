"""A Simple script to evaluate the agent trajectory.

Need to install agentevals:

```
pip install agentevals
```
"""

import json
import os
from argparse import ArgumentParser

from agentevals.trajectory.llm import TRAJECTORY_ACCURACY_PROMPT, create_trajectory_llm_as_judge  # type: ignore

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--trajectory-path", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)

    args = parser.parse_args()

    dataset = []
    for file in os.listdir(args.trajectory_path):
        with open(os.path.join(args.trajectory_path, file), "r") as f:
            parsed_trajectory = json.load(f)
        agentevals_trajectories = []
        for trajectory in parsed_trajectory:
            if isinstance(trajectory["content"], str):
                agentevals_trajectories.append(
                    {
                        "role": trajectory["role"],
                        "content": trajectory["content"],
                    }
                )

            elif isinstance(trajectory["content"], list):
                tool_calls = []
                tool_results = ""
                for content in trajectory["content"]:
                    if content["type"] == "tool_use":
                        tool_calls.append(
                            {"function": {"name": content["name"], "arguments": json.dumps(content["input"])}}
                        )
                    elif content["type"] == "tool_result":
                        tool_results += content["content"]

                if tool_calls:
                    agentevals_trajectories.append(
                        {"role": trajectory["role"], "content": "", "tool_calls": tool_calls}
                    )

                if tool_results:
                    agentevals_trajectories.append({"role": "tool", "content": tool_results})

        dataset.append(agentevals_trajectories)

    # evaluate
    trajectory_evaluator = create_trajectory_llm_as_judge(
        prompt=TRAJECTORY_ACCURACY_PROMPT,
        model="openai:o3-mini",
    )

    results = []
    scores = []
    for data in dataset:
        eval_result = trajectory_evaluator(
            outputs=data,
        )
        scores.append(int(eval_result["score"]))
        results.append(eval_result)

    print("Score:", sum(scores) / len(scores))

    with open(args.output, "w") as f:
        f.write(json.dumps(results, indent=2, ensure_ascii=False))
