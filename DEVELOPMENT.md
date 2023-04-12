# Developer Guide

This guide is intended to provide an overview of the CrowdStrike CWP / Horizon Benchmark Utilities project and explain how to contribute to the development of the benchmark scripts for AWS, Azure, and GCP.

## Project Overview

The project aims to provide a set of scripts for auditing cloud resources across AWS, Azure, and GCP. The main `benchmark.sh` script handles argument parsing, checking for Python3 and pip installations, and running the appropriate benchmarking script for each supported cloud provider. The benchmarking scripts themselves are written in Python, and the main script downloads the necessary files and installs Python dependencies before running them.

## Directory Structure

The project is structured as follows:

```terminal
.
├── AWS
│   ├── README.md
│   ├── requirements.txt
│   └── aws_cspm_benchmark.py
├── Azure
│   ├── README.md
│   ├── requirements.txt
│   └── azure_cspm_benchmark.py
├── GCP
│   ├── README.md
│   ├── requirements.txt
│   └── gcp_cspm_benchmark.py
└── benchmark.sh
```

Each cloud provider has its own directory, containing a README file, a requirements.txt file for Python dependencies, and the corresponding benchmark script.

## Contributing to the Benchmark Scripts

To contribute to the development of the benchmark scripts, follow these steps:

1. **Fork the repository**: Create a fork of the main repository on your GitHub account.

2. **Clone your fork**: Clone your fork of the repository to your local machine.

3. **Set up a virtual environment**: It's a good practice to set up a virtual environment for your development work. You can do this by running:

   ```shell
   python3 -m venv ./cloud-benchmark-dev
   source ./cloud-benchmark-dev/bin/activate
   ```

4. **Install Python dependencies**: Install the necessary Python dependencies for the cloud provider you're working on:

   ```shell
   pip3 install -r path/to/provider/requirements.txt
   ```

5. **Modify the benchmark script**: Make changes to the appropriate benchmark script (e.g., `aws_cspm_benchmark.py`, `azure_cspm_benchmark.py`, or `gcp_cspm_benchmark.py`) according to your contribution.

6. **Test your changes**: Run the modified benchmark script to test your changes and ensure they work as expected.

7. **Commit and push your changes**: Commit your changes to your fork and push them to your remote GitHub repository.

8. **Create a pull request**: Open a pull request to merge your changes into the main repository.

## Coding Guidelines

When contributing to the benchmark scripts, keep these coding guidelines in mind:

- Follow the [PEP 8 style guide](https://www.python.org/dev/peps/pep-0008/) for Python code.
- Use meaningful variable and function names.
- Include docstrings for functions and classes to explain their purpose and usage.
- Keep functions small and focused on a single task.

By following these guidelines and the contribution steps outlined above, you can help improve this project and make it more useful for everyone.
