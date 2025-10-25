import os
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()

class Settings:
    """Configuration settings"""
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "XX")
    AZURE_OPENAI_ENDPOINT = "https://devops-buddy.openai.azure.com/"
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_API_DEPLOYMENT_NAME", "")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-04-01-preview")
    
    
    GITHUB_TOKEN = os.getenv("GITHUB_API_TOKEN", "")
    GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
    
    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_URI", "localhost:27017")
    MONGO_DATABASE = os.getenv("MONGO_DATABASE", "dev-ops-buddy")
    MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "JiraIssues")
    MONGO_TIMEOUT = int(os.getenv("MONGO_TIMEOUT", "30"))
    
    # Jenkins Configuration
    JENKINS_PRD_URL = os.getenv("JENKINS_PRD_BASE_URL", "https://jenkins-prd.meeshogcp.in")
    JENKINS_PROXY_BASE_URL = os.getenv("JENKINS_PROXY_BASE_URL", "https://jenkins-dev-proxy.admin.meeshogcp.in")
    JENKINS_DEV_URL = os.getenv("JENKINS_DEV_BASE_URL", "https://jenkins-dev.meeshogcp.in")
    
    # Jenkins Credentials
    JENKINS_PRD_USERNAME = os.getenv("JENKINS_PRD_USERNAME", "")
    JENKINS_PRD_TOKEN = os.getenv("JENKINS_PRD_TOKEN", "")
    JENKINS_PROXY_USERNAME = os.getenv("JENKINS_PROXY_USERNAME", "")
    JENKINS_PROXY_TOKEN = os.getenv("JENKINS_PROXY_TOKEN", "")
    JENKINS_DEV_USERNAME = os.getenv("JENKINS_DEV_USERNAME", "")
    JENKINS_DEV_TOKEN = os.getenv("JENKINS_DEV_TOKEN", "")
    
    @classmethod
    def get_azure_config(cls) -> Dict[str, Any]:
        """Get Azure OpenAI configuration"""
        return {
            "azure_endpoint": cls.AZURE_OPENAI_ENDPOINT,
            "api_version": cls.AZURE_OPENAI_API_VERSION,
            "azure_deployment": cls.AZURE_OPENAI_DEPLOYMENT,
            "api_key": cls.AZURE_OPENAI_API_KEY,
            "temperature": 0.1,
            "max_tokens": 4000
        }
    
    @classmethod
    def get_github_config(cls) -> Dict[str, Any]:
        """Get GitHub configuration"""
        return {
            "token": cls.GITHUB_TOKEN,
            "mcp_url": cls.GITHUB_MCP_URL
        }
    
    @classmethod
    def get_mongodb_config(cls) -> Dict[str, Any]:
        """Get MongoDB configuration"""
        return {
            "uri": cls.MONGO_URI,
            "database": cls.MONGO_DATABASE,
            "collection": cls.MONGO_COLLECTION,
            "timeout": cls.MONGO_TIMEOUT
        }
    
    @classmethod
    def get_jenkins_config(cls) -> Dict[str, Any]:
        """Get Jenkins configuration"""
        return {
            "urls": {
                "production": cls.JENKINS_PRD_URL,
                "dev-proxy": cls.JENKINS_PROXY_BASE_URL,
                "development": cls.JENKINS_DEV_URL
            },
            "credentials": {
                "production": {
                    "username": cls.JENKINS_PRD_USERNAME,
                    "token": cls.JENKINS_PRD_TOKEN
                },
                "dev-proxy": {
                    "username": cls.JENKINS_PROXY_USERNAME,
                    "token": cls.JENKINS_PROXY_TOKEN
                },
                "development": {
                    "username": cls.JENKINS_DEV_USERNAME,
                    "token": cls.JENKINS_DEV_TOKEN
                }
            }
        }


