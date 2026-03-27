# planner/topological_sort.py
# verify : done

from collections import defaultdict, deque
from typing import List, Dict, Any


def topological_sort_steps(plan: List[Dict[str, Any]], autofix: bool = False, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Sorts the execution plan topologically based on 'depends_on' field.

    Parameters:
        plan (List[Dict]): List of step dicts with a path/target_path and optional 'depends_on'.
        autofix (bool): If True, invalid dependencies are ignored instead of throwing an error.
        debug (bool): If True, prints the dependency graph.

    Returns:
        List[Dict]: Sorted list of steps.

    Raises:
        ValueError: If unknown dependencies or cyclic dependencies are detected (unless autofix is True).
    """
    graph = defaultdict(list)    # adjacency list
    in_degree = defaultdict(int)

    def _step_key(step, fallback: str):
        return step.get("path") or step.get("target_path") or step.get("id") or fallback

    step_keys = []
    for idx, step in enumerate(plan):
        step_keys.append(_step_key(step, f"step-{idx}"))

    path_to_index = {key: idx for idx, key in enumerate(step_keys)}
    indexed_plan = list(enumerate(plan))

    # Validate all dependencies first
    for idx, step in indexed_plan:
        step_path = _step_key(step, f"step-{idx}")
        depends = step.get("depends_on", [])

        if not isinstance(depends, list):
            raise ValueError(f"Invalid 'depends_on' format in step {step_path}, must be a list.")

        for dep_path in depends:
            if dep_path not in path_to_index:
                message = f"Step '{step_path}' depends on unknown file: '{dep_path}'"
                if autofix:
                    print(f"[AutoFix] {message} -- Skipping this dependency.")
                    continue
                else:
                    raise ValueError(message)

            from_idx = path_to_index[dep_path]
            graph[from_idx].append(idx)
            in_degree[idx] += 1

    if debug:
        print("\nDependency Graph:")
        for k, v in graph.items():
            from_path = _step_key(plan[k], f"step-{k}")
            to_paths = [_step_key(plan[i], f"step-{i}") for i in v]
            print(f"  {from_path} -> {to_paths}")

    # Start with all nodes that have no dependencies
    queue = deque([idx for idx, _ in indexed_plan if in_degree[idx] == 0])
    sorted_indices = []

    while queue:
        node = queue.popleft()
        sorted_indices.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_indices) != len(plan):
        # Find cycle paths
        unresolved = [_step_key(plan[i], f"step-{i}") for i in range(len(plan)) if i not in sorted_indices]
        raise ValueError(f"Cyclic dependency detected among steps: {unresolved}")

    return [plan[i] for i in sorted_indices]
