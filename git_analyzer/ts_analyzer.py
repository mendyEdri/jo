import os
import json
from typing import Dict, List, Set
import subprocess
from pathlib import Path
import click
import tempfile
import sys
from typing import Callable
import shutil

class TypeScriptAnalyzer:
    def __init__(self, repo_path: str, is_ignored_func: Callable[[Path], bool] = None):
        self.repo_path = os.path.abspath(repo_path)
        self.temp_dir = None
        self.is_ignored = is_ignored_func or (lambda _: False)
        self.analyzed_files = set()  # Track analyzed files
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if required Node.js dependencies are installed"""
        if not shutil.which('node'):
            raise Exception(
                "Node.js is not installed. Please install Node.js from https://nodejs.org"
            )
        
        if not shutil.which('ts-node'):
            click.secho("\nMissing required dependency: ts-node", fg='yellow', err=True)
            click.secho("Installing ts-node globally...", fg='yellow', err=True)
            try:
                subprocess.run(['npm', 'install', '-g', 'ts-node', 'typescript'], check=True)
                click.secho("Successfully installed ts-node!", fg='green', err=True)
            except subprocess.CalledProcessError as e:
                raise Exception(
                    "Failed to install ts-node. Please install it manually:\n"
                    "npm install -g ts-node typescript"
                ) from e
            except FileNotFoundError:
                raise Exception(
                    "npm not found. Please install Node.js from https://nodejs.org"
                )

    def analyze(self) -> Dict:
        """Analyze TypeScript files in the repository"""
        ts_files = []
        
        # Walk through repository and collect TypeScript files
        for root, dirs, files in os.walk(self.repo_path):
            # Skip node_modules directory entirely
            if 'node_modules' in dirs:
                dirs.remove('node_modules')  # This prevents os.walk from recursing into node_modules
            
            for file in files:
                if file.endswith(('.ts', '.tsx')):
                    file_path = Path(os.path.join(root, file))
                    if not self.is_ignored(file_path):
                        ts_files.append(file_path)
        
        if not ts_files:
            return {
                'functions': {},
                'classes': {},
                'interfaces': {},
                'types': {},
                'dependencies': {}
            }

        # Create temporary directory for analysis
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_dir = temp_dir
            
            # Create analysis script
            self._create_analysis_script()
            
            results = {
                'functions': {},
                'classes': {},
                'interfaces': {},
                'types': {}
            }
            
            # Process files with progress bar
            with click.progressbar(
                ts_files,
                label=click.style('Analyzing TypeScript files', fg='blue'),
                item_show_func=lambda p: click.style(f'→ {p.name if p else ""}', fg='bright_black'),
                show_pos=True,
                show_percent=True,
                bar_template='\r%(label)s  [%(bar)s]  %(info)s',
                fill_char=click.style('█', fg='blue'),
                empty_char='░',
                file=sys.stderr
            ) as files:
                for file_path in files:
                    try:
                        file_results = self._analyze_file(file_path)
                        self._merge_results(results, file_results)
                        self.analyzed_files.add(file_path)  # Add file to analyzed files
                    except Exception as e:
                        # Clear the current line before showing error
                        click.echo('\r' + ' ' * 100 + '\r', nl=False, err=True)
                        click.secho(f"Error analyzing {file_path}: {str(e)}", fg='red', err=True)
                        continue
            
            # Clear the progress line
            click.echo('\r' + ' ' * 100 + '\r', nl=False, err=True)
            return {
                'repository': self.repo_path,
                'functions': results['functions'],
                'classes': results['classes'],
                'interfaces': results['interfaces'],
                'types': results['types'],
                'dependencies': {}
            }

    def _create_analysis_script(self):
        """Create temporary TypeScript analysis script"""
        script_content = """
        import * as ts from 'typescript';
        import * as fs from 'fs';

        const fileName = process.argv[2];
        try {
            const sourceFile = ts.createSourceFile(
                fileName,
                fs.readFileSync(fileName, 'utf-8'),
                ts.ScriptTarget.Latest,
                true
            );

            const results = {
                functions: {},
                classes: {},
                interfaces: {},
                types: {}
            };

            function visit(node: ts.Node) {
                if (ts.isFunctionDeclaration(node)) {
                    const name = node.name?.getText() || 'anonymous';
                    results.functions[name] = {
                        file: fileName,
                        line: sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1,
                        parameters: node.parameters.map(p => ({
                            name: p.name.getText(),
                            type: p.type ? p.type.getText() : 'any'
                        })),
                        returnType: node.type ? node.type.getText() : 'void'
                    };
                }
                else if (ts.isClassDeclaration(node)) {
                    const name = node.name?.getText() || 'anonymous';
                    results.classes[name] = {
                        file: fileName,
                        line: sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1,
                        properties: node.members
                            .filter(ts.isPropertyDeclaration)
                            .map(p => p.name.getText()),
                        methods: node.members
                            .filter(ts.isMethodDeclaration)
                            .map(m => m.name.getText()),
                        extends: node.heritageClauses
                            ?.filter(h => h.token === ts.SyntaxKind.ExtendsKeyword)
                            .flatMap(h => h.types.map(t => t.getText())) || []
                    };
                }
                else if (ts.isInterfaceDeclaration(node)) {
                    const name = node.name.getText();
                    results.interfaces[name] = {
                        file: fileName,
                        line: sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1,
                        properties: node.members
                            .filter(ts.isPropertySignature)
                            .map(p => ({
                                name: p.name.getText(),
                                type: p.type ? p.type.getText() : 'any'
                            }))
                    };
                }
                else if (ts.isTypeAliasDeclaration(node)) {
                    const name = node.name.getText();
                    results.types[name] = {
                        file: fileName,
                        line: sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1,
                        type: node.type.getText()
                    };
                }

                ts.forEachChild(node, visit);
            }

            visit(sourceFile);
            console.log(JSON.stringify(results));
        } catch (error) {
            console.error(error.message);
            process.exit(1);
        }
        """
        
        script_path = os.path.join(self.temp_dir, 'analyzer.ts')
        with open(script_path, 'w') as f:
            f.write(script_content)

    def _analyze_file(self, file_path):
        """Analyze a single TypeScript file"""
        try:
            # Add timeout to prevent hanging
            result = subprocess.run(
                ['ts-node', os.path.join(self.temp_dir, 'analyzer.ts'), str(file_path)],
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception on non-zero exit
                timeout=30  # 30 second timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"TypeScript analysis failed: {result.stderr}")
            
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                raise Exception("Failed to parse TypeScript analysis results")
                
        except subprocess.TimeoutExpired:
            raise Exception("Analysis timed out after 30 seconds")
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")

    def _merge_results(self, target, source):
        """Merge analysis results"""
        for category in ['functions', 'classes', 'interfaces', 'types']:
            target[category].update(source.get(category, {}))

    def _get_typescript_files(self) -> List[Path]:
        """Get all TypeScript files in the repository"""
        ts_files = list(Path(self.repo_path).rglob("*.ts"))
        tsx_files = list(Path(self.repo_path).rglob("*.tsx"))
        return ts_files + tsx_files

    def _process_analysis_result(self, file_path: str, analysis: Dict):
        """Process the analysis result from the TypeScript analyzer"""
        # Add file path to all items
        for name, func in analysis.get('functions', {}).items():
            func['file'] = file_path
            self.functions[name] = func
        
        for name, cls in analysis.get('classes', {}).items():
            cls['file'] = file_path
            self.classes[name] = cls
        
        for name, iface in analysis.get('interfaces', {}).items():
            iface['file'] = file_path
            self.interfaces[name] = iface
        
        for name, type_info in analysis.get('types', {}).items():
            type_info['file'] = file_path
            self.types[name] = type_info
