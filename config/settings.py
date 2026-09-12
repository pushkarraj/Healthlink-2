from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    #LLM Configuration
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2500

    #Embedding Configuration
    embedding_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    
    
    #Pinecone Configuration
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index: str = "healthlink"

    #RAG Configuration
    rag_k: int = 5
    chunk_size: int = 500
    chunk_overlap: int = 50

    #Database Configuration
    database_url: str = "sqlite:///./healthlink.db"
    db_echo: bool = False

    #API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: List[str] = ["*"]

    #Logging Configuration
    log_level: str = "INFO"

    #Security Configuration
    secret_key: str = ""

    # Google Cloud Configuration
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us-central1"
    
    def validate_config(self):
        if not self.llm_api_key:
            raise ValueError("LLM API key is required")
        if not self.embedding_api_key:
            raise ValueError("Embedding API key is required")
        if not self.pinecone_api_key:
            raise ValueError("Pinecone API key is required")
        if not self.google_cloud_project_id:
            raise ValueError("Google Cloud project ID is required")
        if not self.google_cloud_location:
            raise ValueError("Google Cloud location is required")

    def get_settings() -> Settings:
        settings = Settings()
        settings.validate_config()
        return settings






