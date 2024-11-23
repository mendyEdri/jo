"""
AST analysis module for Python code
"""
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional
import os
import click
from dataclasses import dataclass, field

@dataclass
class ASTNode:
    """Represents a node in the AST"""
    name: str
    type: str
    line: int
    end_line: int
    col_offset: int
    end_col_offset: int
    parent: Optional['ASTNode'] = None
    children: List['ASTNode'] = field(default_factory=list)
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    assignments: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    file_path: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert node to dictionary representation"""
        return {
            'name': self.name,
            'type': self.type,
            'line': self.line,
            'end_line': self.end_line,
            'col_offset': self.col_offset,
            'end_col_offset': self.end_col_offset,
            'docstring': self.docstring,
            'decorators': self.decorators,
            'returns': self.returns,
            'arguments': self.arguments,
            'bases': self.bases,
            'assignments': self.assignments,
            'calls': self.calls,
            'file_path': self.file_path,
            'children': [child.to_dict() for child in self.children]
        }

class ASTVisitor(ast.NodeVisitor):
    """Visit AST nodes and build ASTNode structure"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nodes: List[ASTNode] = []
        self.current_class = None
        self.current_function = None
        self.scope_stack = []
        
    def visit_ClassDef(self, node: ast.ClassDef):
        """Process class definition"""
        ast_node = ASTNode(
            name=node.name,
            type='class',
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            col_offset=node.col_offset,
            end_col_offset=node.end_col_offset or 0,
            docstring=ast.get_docstring(node),
            bases=[self._get_name(base) for base in node.bases],
            file_path=self.file_path
        )
        
        # Handle decorators
        if hasattr(node, 'decorator_list'):
            ast_node.decorators = [self._get_name(d) for d in node.decorator_list]
            
        self._add_node(ast_node)
        
        old_class = self.current_class
        self.current_class = ast_node
        self.scope_stack.append(ast_node)
        
        # Visit children
        for child in node.body:
            self.visit(child)
            
        self.scope_stack.pop()
        self.current_class = old_class
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process function definition"""
        self._process_function(node)
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Process async function definition"""
        self._process_function(node, is_async=True)
        
    def visit_Call(self, node: ast.Call):
        """Process function calls"""
        if self.scope_stack:
            current = self.scope_stack[-1]
            current.calls.append(self._get_name(node.func))
        self.generic_visit(node)
        
    def visit_Assign(self, node: ast.Assign):
        """Process assignments"""
        if self.scope_stack:
            current = self.scope_stack[-1]
            for target in node.targets:
                current.assignments.append(self._get_name(target))
        self.generic_visit(node)
        
    def _process_function(self, node: ast.FunctionDef, is_async: bool = False):
        """Process function definition (sync or async)"""
        ast_node = ASTNode(
            name=node.name,
            type='async_function' if is_async else 'function',
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            col_offset=node.col_offset,
            end_col_offset=node.end_col_offset or 0,
            docstring=ast.get_docstring(node),
            arguments=self._get_arguments(node.args),
            file_path=self.file_path
        )
        
        # Handle return annotation
        if node.returns:
            ast_node.returns = self._get_name(node.returns)
            
        # Handle decorators
        if hasattr(node, 'decorator_list'):
            ast_node.decorators = [self._get_name(d) for d in node.decorator_list]
            
        self._add_node(ast_node)
        
        old_function = self.current_function
        self.current_function = ast_node
        self.scope_stack.append(ast_node)
        
        # Visit children
        for child in node.body:
            self.visit(child)
            
        self.scope_stack.pop()
        self.current_function = old_function
        
    def _add_node(self, node: ASTNode):
        """Add node to the tree structure"""
        if self.scope_stack:
            parent = self.scope_stack[-1]
            node.parent = parent
            parent.children.append(node)
        self.nodes.append(node)
        
    def _get_arguments(self, args: ast.arguments) -> List[str]:
        """Extract function arguments"""
        arguments = []
        
        # Add positional args
        for arg in args.posonlyargs + args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_name(arg.annotation)}"
            arguments.append(arg_str)
            
        # Add varargs
        if args.vararg:
            arguments.append(f"*{args.vararg.arg}")
            
        # Add keyword args
        for arg in args.kwonlyargs:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_name(arg.annotation)}"
            arguments.append(arg_str)
            
        # Add kwargs
        if args.kwarg:
            arguments.append(f"**{args.kwarg.arg}")
            
        return arguments
        
    def _get_name(self, node) -> str:
        """Get string representation of a node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return str(node.n)
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return str(node)

class ASTAnalyzer:
    """Analyze Python files and build AST structure"""
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.ast_nodes: List[ASTNode] = []
        
    def analyze(self) -> Dict:
        """Analyze Python files and build AST structure"""
        python_files = self._get_python_files()
        
        if not python_files:
            click.secho("No Python files found to analyze.", fg='yellow', err=True)
            return {'files': [], 'nodes': []}
            
        with click.progressbar(
            python_files,
            label=click.style('Building AST', fg='green'),
            item_show_func=lambda p: click.style(f'→ {p.name if p else ""}', fg='bright_black'),
            show_pos=True,
            show_percent=True,
            bar_template='\r%(label)s  [%(bar)s]  %(info)s',
            fill_char=click.style('█', fg='green'),
            empty_char='░'
        ) as files:
            for file_path in files:
                try:
                    self._analyze_file(file_path)
                except Exception as e:
                    click.secho(f"Error analyzing {file_path}: {str(e)}", fg='red', err=True)
                    
        return {
            'files': [str(f) for f in python_files],
            'nodes': [node.to_dict() for node in self.ast_nodes]
        }
        
    def analyze_string(self, code: str) -> Dict:
        """Analyze Python code string"""
        try:
            tree = ast.parse(code)
            visitor = ASTVisitor("<string>")
            visitor.visit(tree)
            return {
                'files': ["<string>"],
                'nodes': [node.to_dict() for node in visitor.nodes]
            }
        except Exception as e:
            click.secho(f"Error analyzing code: {str(e)}", fg='red', err=True)
            return {'files': [], 'nodes': []}
        
    def _get_python_files(self) -> List[Path]:
        """Get all Python files in the repository"""
        python_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'node_modules', '__pycache__', '.git', 'venv', 'env'}]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(os.path.join(root, file)))
        return python_files
        
    def _analyze_file(self, file_path: Path):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
                visitor = ASTVisitor(str(file_path))
                visitor.visit(tree)
                self.ast_nodes.extend(visitor.nodes)
        except Exception as e:
            raise Exception(f"Failed to analyze {file_path}: {str(e)}")