# DockerInterpreter Tool

## Description

This is an openwebui tool that can run arbitrary Python code (other languages might be added in the future). It uses Docker tooling for isolation, allowing further security by using different Docker engines (e.g., gVisor's runsc). The openwebui Docker image has every package needed to run it.

The main use case is to couple it with system prompts to implement assistants like a data analyst, a coding instructor, etc. It's based/inspired by [EtiennePerot/open-webui-code-execution](https://github.com/EtiennePerot/open-webui-code-execution).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/smonux/open-webui-docker-execution.git
   cd open-webui-docker-execution
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements-pythonds.txt
   ```

3. Ensure Docker is installed and running on your system.

## Usage

1. Start the Docker container:
   ```bash
   docker-compose -f openwebui-compose-dev.yml up
   ```

2. Run the Python code interpreter:
   ```bash
   python runcode.py
   ```

3. For LLM checks, use:
   ```bash
   python runllmcheck-single.py --prompt "Your prompt here"
   ```

   or for multi-iteration checks:
   ```bash
   python runllmcheck-multi.py --prompt "Your prompt here" --max_iterations 5
   ```

## Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
