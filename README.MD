# Jo - Git Codebase Analyzer

A command-line tool for analyzing Git repositories and extracting code structure information. Supports both Python and TypeScript codebases.

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Node.js dependencies (required for TypeScript analysis):
```bash
npm install -g typescript
npm install -g ts-node
```

## Usage

1. Start analyzing a Git repository:
```bash
jo start /path/to/repository
```

2. View the detailed analysis:
```bash
jo map /path/to/repository
```

You can also get the output in JSON format:
```bash
jo map /path/to/repository --format json
```

Clear all cached analyses:
```bash
jo drop
```

The analysis will:
1. Analyze all Python and TypeScript files in the repository
2. Extract information about:
   - Functions and methods (with parameters and return types for TypeScript)
   - Classes (with properties and inheritance for TypeScript)
   - Interfaces (TypeScript)
   - Type aliases (TypeScript)
3. Store relationships between code elements
4. Cache results in a local SQLite database

## Features

- Extracts functions, methods, and classes from Python code
- Analyzes TypeScript-specific features:
  * Interfaces and their properties
  * Type aliases and definitions
  * Function parameter types and return types
  * Class properties and inheritance
- Stores results in a local cache for quick access
- Simple command-line interface
- Multiple output formats (text and JSON)

## Requirements

- Python 3.6+
- Node.js 14+ and npm (for TypeScript analysis)
- Git