import subprocess
import sys
from pathlib import Path


FILENAME = "solve_cb.py"
TIMEOUT = 3600


INSTANCES = [
	("MERTENS", 6, 6),
	("MERTENS", 2, 18),
	("BOWMAN", 5, 20),
	("JAESCHKE", 8, 6),
	("JAESCHKE", 3, 18),
	("JACKSON", 8, 7),
	("JACKSON", 3, 21),
	("MANSOOR", 4, 48),
	("MANSOOR", 2, 94),
	("MITCHELL", 8, 14),
	("MITCHELL", 3, 39),
	("ROSZIEG", 10, 14),
	("ROSZIEG", 4, 32),
	("BUXEY", 7, 47),
	("BUXEY", 14, 25),
	("SAWYER", 14, 25),
	("SAWYER", 7, 47),
]


def run_instances(filename, timeout, instances):
	"""Run filename once for every (name, machines, cycle) tuple."""
	script = Path(filename)
	if not script.is_file():
		raise FileNotFoundError(f"Cannot find solver script: {script}")

	for name, machines, cycle in instances:
		command = [sys.executable, str(script), name, str(machines), str(cycle)]
		print(f"\n{'=' * 50}")
		print(
			f"Running: {name} (Machines={machines}, Cycle={cycle}) | "
			f"Timeout: {timeout}s"
		)
		print(f"{'=' * 50}")
		try:
			completed = subprocess.run(command, timeout=timeout, check=False)
		except subprocess.TimeoutExpired:
			print(f"--> TIMEOUT: {name} ({machines}, {cycle})")
			continue

		if completed.returncode != 0:
			print(
				f"--> FAILED: {name} ({machines}, {cycle}) "
				f"(exit code {completed.returncode})"
			)


def main():
	run_instances(FILENAME, TIMEOUT, INSTANCES)


if __name__ == "__main__":
	main()
