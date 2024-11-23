"""
Code embeddings manager for semantic search
"""
import os
from dataclasses import dataclass, field
import numpy as np
from openai import OpenAI
import pickle
from typing import List, Dict, Tuple, Optional

@dataclass
class CodeItem:
    name: str
    type: str
    file_path: str
    content: str
    embedding: Optional[List[float]] = None

class EmbeddingManager:
    def __init__(self):
        """Initialize the embedding manager"""
        self.items: List[CodeItem] = []
        self._cache_dir = os.path.expanduser("~/.jo/embeddings")
        self._cache_file = "embeddings.pkl"
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY environment variable not set")
            
        self.client = OpenAI(api_key=api_key)
            
        # Create cache directory if it doesn't exist
        os.makedirs(self._cache_dir, exist_ok=True)
        
        # Load cached items if they exist
        self._load_cache()
    
    def add_item(self, item: CodeItem):
        """Add a code item to be embedded"""
        self.items.append(item)
    
    def process_analysis_results(self, nodes: List[Dict]):
        """Process analysis results and extract code items"""
        def process_node(node: Dict):
            # Add the current node
            self.add_item(CodeItem(
                name=node['name'],
                type=node['type'],
                file_path=node.get('file_path', ''),
                content=self._extract_content(node)
            ))
            
            # Process children recursively
            for child in node.get('children', []):
                process_node(child)
                
        # Process each top-level node
        for node in nodes:
            process_node(node)
            
    def _extract_content(self, info: Dict) -> str:
        """Extract meaningful content from item info"""
        content_parts = []
        
        # Add docstring
        if info.get('docstring'):
            content_parts.append(f"Description: {info['docstring']}")
            
        # Add arguments for functions
        if info.get('arguments'):
            params = ", ".join(str(arg) for arg in info['arguments'])
            content_parts.append(f"Parameters: {params}")
            
        # Add return type for functions
        if info.get('returns'):
            content_parts.append(f"Returns: {info['returns']}")
            
        # Add bases for classes
        if info.get('bases'):
            bases = ", ".join(str(base) for base in info['bases'])
            content_parts.append(f"Inherits from: {bases}")
            
        # Add function calls
        if info.get('calls'):
            calls = ", ".join(str(call) for call in info['calls'])
            content_parts.append(f"Calls: {calls}")
            
        # Add assignments
        if info.get('assignments'):
            assigns = ", ".join(str(assign) for assign in info['assignments'])
            content_parts.append(f"Assigns: {assigns}")
            
        return " | ".join(content_parts)
    
    def generate_embeddings(self):
        """Generate embeddings for all code items"""
        if not self.items:
            return
            
        # Generate embeddings for items that don't have them
        items_to_embed = [item for item in self.items if item.embedding is None]
        if not items_to_embed:
            return
            
        try:
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=[f"{item.name}: {item.content}" for item in items_to_embed]
            )
            
            # Update items with embeddings
            for item, embedding_data in zip(items_to_embed, response.data):
                item.embedding = embedding_data.embedding
                
            # Save to cache
            self._save_cache()
                
        except Exception as e:
            raise Exception(f"Failed to generate embeddings: {str(e)}")
    
    def find_similar(self, query: str, limit: int = 5, threshold: float = 0.7) -> List[Tuple[CodeItem, float]]:
        """Find code items similar to the query"""
        try:
            # Generate embedding for query
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=[query]
            )
            query_embedding = response.data[0].embedding
            
            # Calculate similarity scores
            results = []
            for item in self.items:
                if item.embedding is None:
                    continue
                    
                similarity = self._cosine_similarity(query_embedding, item.embedding)
                if similarity >= threshold:
                    results.append((item, similarity))
            
            # Sort by similarity score
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
            
        except Exception as e:
            raise Exception(f"Failed to find similar items: {str(e)}")
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def calculate_similarity(self, query: str, content: str) -> float:
        """Calculate similarity between a query and a piece of content"""
        try:
            # Generate embeddings for both query and content
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=[query, content]
            )
            
            # Get embeddings from response
            query_embedding = response.data[0].embedding
            content_embedding = response.data[1].embedding
            
            # Calculate similarity
            return self._cosine_similarity(query_embedding, content_embedding)
            
        except Exception as e:
            raise Exception(f"Failed to calculate similarity: {str(e)}")
    
    def _save_cache(self):
        """Save embeddings to cache"""
        cache_path = os.path.join(self._cache_dir, self._cache_file)
        with open(cache_path, 'wb') as f:
            pickle.dump(self.items, f)
    
    def _load_cache(self):
        """Load embeddings from cache"""
        cache_path = os.path.join(self._cache_dir, self._cache_file)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    self.items = pickle.load(f)
            except:
                self.items = []
