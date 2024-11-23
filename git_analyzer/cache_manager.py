import os
import json
from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import click
import shutil

Base = declarative_base()

class Analysis(Base):
    __tablename__ = 'analyses'
    
    id = Column(Integer, primary_key=True)
    repository = Column(String, unique=True)
    functions = Column(JSON)
    classes = Column(JSON)
    interfaces = Column(JSON)
    types = Column(JSON)
    dependencies = Column(JSON)

class CacheManager:
    def __init__(self):
        self.cache_dir = os.path.expanduser("~/.jo/cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.cache_dir, "analyses.db")
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def drop_cache(self):
        """Drop all cached analyses and remove the cache directory"""
        try:
            # Close existing session and connection
            self.session.close()
            self.engine.dispose()
            
            # Remove the entire cache directory
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            
            # Recreate cache directory and database
            os.makedirs(self.cache_dir, exist_ok=True)
            self.engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            
            return True
        except Exception as e:
            click.secho(f"Error dropping cache: {str(e)}", fg='red', err=True)
            return False

    def save_analysis(self, results):
        """Save analysis results to cache"""
        repo_path = os.path.abspath(results['repository'])
        
        # Check if analysis exists
        analysis = self.session.query(Analysis).filter_by(repository=repo_path).first()
        
        if analysis:
            # Update existing analysis
            analysis.functions = results.get('functions', {})
            analysis.classes = results.get('classes', {})
            analysis.interfaces = results.get('interfaces', {})
            analysis.types = results.get('types', {})
            analysis.dependencies = results.get('dependencies', {})
        else:
            # Create new analysis
            analysis = Analysis(
                repository=repo_path,
                functions=results.get('functions', {}),
                classes=results.get('classes', {}),
                interfaces=results.get('interfaces', {}),
                types=results.get('types', {}),
                dependencies=results.get('dependencies', {})
            )
            self.session.add(analysis)
        
        self.session.commit()
    
    def get_analysis(self, repo_path):
        """Get analysis results from cache"""
        repo_path = os.path.abspath(repo_path)
        analysis = self.session.query(Analysis).filter_by(repository=repo_path).first()
        
        if not analysis:
            return None
        
        return {
            'repository': analysis.repository,
            'functions': analysis.functions,
            'classes': analysis.classes,
            'interfaces': analysis.interfaces,
            'types': analysis.types,
            'dependencies': analysis.dependencies
        }