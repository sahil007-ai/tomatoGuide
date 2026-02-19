import os


class AdaptiveTimer:
    def __init__(self, current_optimal_mins=25.0, memory_path="focus_memory.txt"):
        self.memory_path = memory_path
        self.optimal_mins = self._load_or_default(current_optimal_mins)
        self.learning_rate = 0.2

    def calculate_next_session(self, distractions):
        if distractions <= 1:
            reward = 1.0
        elif distractions <= 4:
            reward = 0.0
        else:
            reward = -0.5 * (distractions - 4)

        reward = max(-3.0, min(1.0, reward))

        step_size = 5.0
        change = self.learning_rate * reward * step_size

        self.optimal_mins += change
        self.optimal_mins = max(10.0, min(60.0, self.optimal_mins))

        self._save()

        return int(self.optimal_mins)

    def _load_or_default(self, default_value):
        if not self.memory_path:
            return float(default_value)

        if not os.path.exists(self.memory_path):
            return float(default_value)

        try:
            with open(self.memory_path, "r", encoding="utf-8") as handle:
                value = float(handle.read().strip())
        except (OSError, ValueError):
            return float(default_value)

        return max(10.0, min(60.0, value))

    def _save(self):
        if not self.memory_path:
            return

        try:
            with open(self.memory_path, "w", encoding="utf-8") as handle:
                handle.write(f"{self.optimal_mins:.2f}")
        except OSError:
            pass
