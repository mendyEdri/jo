"""
Jo - Python AST analyzer
"""
import json
import os
import sys
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from openai import OpenAI
from .analyzer import ASTAnalyzer
from .embeddings import EmbeddingManager
from typing import Dict

console = Console()

@click.group()
def cli():
    """Jo - Python AST analyzer"""
    pass

@cli.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True), default='.')
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def start(directory, format):
    """Analyze Python files and build AST"""
    try:
        analyzer = ASTAnalyzer(directory)
        results = analyzer.analyze()
        
        if format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            _display_text_results(results)
            
        # Generate embeddings after analysis
        embedding_manager = EmbeddingManager()
        embedding_manager.process_analysis_results(results['nodes'])
        embedding_manager.generate_embeddings()
            
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg='red')
        raise click.Abort()

@cli.command()
@click.argument('query', type=str)
@click.option('--limit', type=int, default=5, help='Number of results to return')
@click.option('--threshold', type=float, default=0.7, help='Similarity threshold (0-1)')
def find(query, limit, threshold):
    """Find code items similar to the query using embeddings"""
    try:
        embedding_manager = EmbeddingManager()
        results = embedding_manager.find_similar(query, limit=limit, threshold=threshold)
        
        if not results:
            click.secho("No matching code items found.", fg='yellow')
            return
            
        click.secho("\nMatching code items:", fg='green', bold=True)
        for i, (item, score) in enumerate(results, 1):
            click.echo(f"\n{i}. {click.style(item.name, fg='blue', bold=True)} ({score:.2f} similarity)")
            click.echo(f"   Type: {click.style(item.type, fg='cyan')}")
            click.echo(f"   File: {click.style(item.file_path, fg='white')}")
            if item.content:
                click.echo(f"   Content:")
                for line in item.content.split('\n'):
                    click.echo(f"     {line}")
                    
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg='red')
        raise click.Abort()

@cli.command()
@click.argument('query', type=str)
def code(query):
    """Find relevant code and generate execution plan"""
    # Find relevant files
    click.secho("\nFinding relevant files...", fg='green')
    relevant_files = find_files(query)
    
    # Filter files with score > 0.75 and sort by score
    high_score_files = {f: s for f, s in relevant_files.items() if s > 0.70}
    if not high_score_files:
        click.secho("No highly relevant files found.", fg='yellow')
        return
    
    # Display relevant files
    click.secho("\nRelevant Files:", fg='green')
    for file, score in sorted(high_score_files.items(), key=lambda x: x[1], reverse=True):
        click.echo(f"[{score:.2f}] {file}")
    
    # Read and analyze file contents
    file_contents = {}
    for file, score in high_score_files.items():
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                file_contents[file] = {
                    'content': content,
                    'score': score,
                    'summary': _analyze_file_content(content)
                }
        except Exception as e:
            click.secho(f"Error reading {file}: {str(e)}", fg='red')
    
    # Generate execution plan
    click.secho("\nGenerating execution plan...", fg='green')
    plan = _generate_execution_plan(query, file_contents)
    click.echo("\n" + plan)
    
    # Generate and apply code changes
    click.secho("\nGenerating code changes...", fg='green')
    for file_path, file_info in file_contents.items():
        click.echo(f"\nProcessing {file_path}...")
        try:
            new_code = _generate_code_changes(
                query=query,
                file_path=file_path,
                current_content=file_info['content'],
                execution_plan=plan
            )
            
            if new_code and new_code.strip() != file_info['content'].strip():
                # Write the changes to the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_code)
                click.secho(f"✓ Updated {file_path}", fg='green')
            else:
                click.secho(f"No changes needed for {file_path}", fg='yellow')
                
        except Exception as e:
            click.secho(f"Error processing {file_path}: {str(e)}", fg='red')

def _analyze_file_content(content: str) -> str:
    """Generate a summary of the file content"""
    client = OpenAI()
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a code analysis assistant. Provide a concise summary of the Python code, focusing on its main components and functionality. Format the response in markdown."},
                {"role": "user", "content": content}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing content: {str(e)}"

def _generate_execution_plan(query: str, file_contents: dict) -> str:
    """Generate an execution plan based on the code query"""
    client = OpenAI()
    
    # Prepare context about available files
    files_context = "\n".join(
        f"- {os.path.basename(file)}:\n{data['summary']}"
        for file, data in file_contents.items()
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a code execution planner. Given a code query and available files, create a detailed plan for implementing the requested functionality. Format your response in markdown with these sections:
                1. Task Breakdown - Break down the task into clear, actionable steps
                2. Implementation Details - Provide specific code changes and additions needed for each step"""},
                {"role": "user", "content": f"Available files:\n{files_context}\n\nCode query: {query}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating plan: {str(e)}"

def _generate_code_changes(query: str, file_path: str, current_content: str, execution_plan: str) -> str:
    """Generate code changes based on the execution plan"""
    client = OpenAI()
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a code generator. Given an execution plan and a file's current content, generate the updated code. Format your response as Python code."},
                {"role": "user", "content": f"File: {file_path}\nCurrent content:\n{current_content}\n\nExecution plan:\n{execution_plan}"}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating code changes: {str(e)}"

def _display_text_results(results):
    """Display results in text format"""
    click.secho("\nAST Analysis Results", fg='green', bold=True)
    click.echo(f"Files analyzed: {len(results['files'])}")
    click.echo(f"Total nodes: {len(results['nodes'])}\n")
    
    def print_node(node, depth=0):
        indent = "  " * depth
        type_color = {
            'class': 'blue',
            'function': 'green',
            'async_function': 'cyan',
        }.get(node['type'], 'white')
        
        # Print name and type
        click.secho(f"{indent}→ {node['name']} ({node['type']})", fg=type_color)
        
        # Print line range
        if 'line' in node and 'end_line' in node:
            click.secho(f"{indent}  Line {node['line']}-{node['end_line']}", fg='bright_black')
            
        # Print bases for classes
        if node.get('bases'):
            click.secho(f"{indent}  Bases: {', '.join(node['bases'])}", fg='yellow')
            
        # Print docstring
        if node.get('docstring'):
            click.secho(f"{indent}  Doc: {node['docstring'].split(chr(10))[0]}", fg='bright_black')
            
        # Print decorators
        if node.get('decorators'):
            click.secho(f"{indent}  Decorators: {', '.join(node['decorators'])}", fg='magenta')
            
        # Print arguments for functions
        if node.get('arguments'):
            click.secho(f"{indent}  Args: {', '.join(node['arguments'])}", fg='yellow')
            
        # Print return type for functions
        if node.get('returns'):
            click.secho(f"{indent}  Returns: {node['returns']}", fg='bright_green')
            
        # Print assignments
        if node.get('assignments'):
            click.secho(f"{indent}  Assigns: {', '.join(node['assignments'])}", fg='bright_black')
            
        # Print function calls
        if node.get('calls'):
            click.secho(f"{indent}  Calls: {', '.join(node['calls'])}", fg='bright_magenta')
            
        # Print children nodes
        for child in node.get('children', []):
            print_node(child, depth + 1)
            
    for node in results['nodes']:
        print_node(node)
        click.echo()

def find_files(query: str) -> Dict[str, float]:
    """Find relevant files and score them based on the query"""
    try:
        # Initialize embedding manager
        manager = EmbeddingManager()
        
        # Get all Python files in current directory
        files = []
        for root, _, filenames in os.walk('.'):
            for filename in filenames:
                if filename.endswith('.py'):
                    files.append(os.path.join(root, filename))
        
        # Score each file
        scores = {}
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    score = manager.calculate_similarity(query, content)
                    scores[file] = score
            except Exception as e:
                click.secho(f"Error reading {file}: {str(e)}", fg='red')
                
        return scores
        
    except Exception as e:
        click.secho(f"Error finding files: {str(e)}", fg='red')
        return {}

if __name__ == '__main__':
    cli()