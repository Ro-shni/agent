#!/usr/bin/env python3
"""
MySQL service for fetching service details and business unit mappings
"""

import asyncio
import aiomysql
from typing import Dict, Any, Optional, List
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MySQLServiceManager:
    """MySQL service manager for service details and business unit mappings"""
    
    def __init__(self):
        self.connection_pool = None
        self.bu_mapping_cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        self.last_cache_update = 0
        
        # MySQL connection details
        self.host = os.getenv("MYSQL_HOST", "")
        self.port = int(os.getenv("MYSQL_PORT", ""))
        self.user = os.getenv("MYSQL_USER", "")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "")
        
    async def initialize(self) -> bool:
        """Initialize MySQL connection pool"""
        try:
            print("🔄 Initializing MySQL connection pool...")
            
            self.connection_pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=1,
                maxsize=10,
                autocommit=True,
                charset='utf8mb4'
            )
            
            print("✅ MySQL connection pool initialized successfully!")
            return True
            
        except Exception as e:
            print(f"❌ MySQL initialization failed: {str(e)}")
            return False
    
    async def close(self):
        """Close MySQL connection pool"""
        if self.connection_pool:
            self.connection_pool.close()
            await self.connection_pool.wait_closed()
            print("✅ MySQL connection pool closed here")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool"""
        if not self.connection_pool:
            raise Exception("MySQL connection pool not initialized")
        
        conn = await self.connection_pool.acquire()
        try:
            yield conn
        finally:
            self.connection_pool.release(conn)
    
    async def get_service_details(self) -> Dict[str, str]:
        """Get service details mapping from MySQL"""
        try:
            # Check cache first
            import time
            current_time = time.time()
            if (current_time - self.last_cache_update) < self.cache_ttl and self.bu_mapping_cache:
                return self.bu_mapping_cache
            
            print("🔄 Fetching service details from MySQL...")
            
            async with self.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT * FROM servicedetails")
                    rows = await cursor.fetchall()
                    
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]
                    
                    # Build mapping
                    bu_mapping = {}
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        deployment = row_dict.get("deployment", "")
                        bu = row_dict.get("bu", "")
                        
                        if deployment and bu:
                            # Remove .yaml extension if present
                            key = deployment.replace(".yaml", "").strip()
                            bu_mapping[key] = bu.strip()
                    
                    # Update cache
                    self.bu_mapping_cache = bu_mapping
                    self.last_cache_update = current_time
                    
                    print(f"✅ Fetched {len(bu_mapping)} service mappings from MySQL")
                    return bu_mapping
                    
        except Exception as e:
            print(f"❌ Failed to fetch service details from MySQL: {str(e)}")
            return {}
    
    async def get_business_unit_for_app(self, app_name: str) -> Optional[str]:
        """Get business unit for a specific application"""
        try:
            bu_mapping = await self.get_service_details()
            print(f"   🔍 MySQL: Looking for app '{app_name}' in {len(bu_mapping)} service mappings")
            result = bu_mapping.get(app_name)
            if result:
                print(f"   ✅ MySQL: Found business unit '{result}' for app '{app_name}'")
            else:
                print(f"   ⚠️ MySQL: No business unit found for app '{app_name}'")
                # Try to find similar app names
                similar_apps = [k for k in bu_mapping.keys() if app_name in k or k in app_name]
                if similar_apps:
                    print(f"   🔍 MySQL: Similar app names found: {similar_apps[:5]}")
            return result
        except Exception as e:
            print(f"❌ Failed to get business unit for {app_name}: {str(e)}")
            return None

    async def get_business_unit_fuzzy_match(self, app_name: str) -> Optional[str]:
        """Get business unit using fuzzy matching for similar app names"""
        try:
            bu_mapping = await self.get_service_details()
            app_name_lower = app_name.lower()
            
            # Try different fuzzy matching strategies
            for existing_app, bu in bu_mapping.items():
                existing_app_lower = existing_app.lower()
                
                # Strategy 1: Check if app_name is contained in existing_app
                if app_name_lower in existing_app_lower:
                    print(f"   🔍 MySQL: Fuzzy match found '{existing_app}' contains '{app_name}' -> BU: {bu}")
                    return bu
                
                # Strategy 2: Check if existing_app is contained in app_name
                if existing_app_lower in app_name_lower:
                    print(f"   🔍 MySQL: Fuzzy match found '{app_name}' contains '{existing_app}' -> BU: {bu}")
                    return bu
                
                # Strategy 3: Check for common prefixes/suffixes
                if (app_name_lower.endswith(existing_app_lower) or 
                    existing_app_lower.endswith(app_name_lower) or
                    app_name_lower.startswith(existing_app_lower) or
                    existing_app_lower.startswith(app_name_lower)):
                    print(f"   🔍 MySQL: Fuzzy match found prefix/suffix match '{existing_app}' <-> '{app_name}' -> BU: {bu}")
                    return bu
            
            print(f"   ⚠️ MySQL: No fuzzy match found for app '{app_name}'")
            return None
        except Exception as e:
            print(f"❌ Failed to fuzzy match business unit for {app_name}: {str(e)}")
            return None
    
    async def search_services_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Search services by pattern"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cursor:
                    query = "SELECT * FROM servicedetails WHERE deployment LIKE %s OR bu LIKE %s"
                    await cursor.execute(query, (f"%{pattern}%", f"%{pattern}%"))
                    rows = await cursor.fetchall()
                    
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]
                    
                    # Convert to list of dictionaries
                    results = []
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        results.append(row_dict)
                    
                    return results
                    
        except Exception as e:
            print(f"❌ Failed to search services: {str(e)}")
            return []


# Global instance
mysql_service = MySQLServiceManager()
