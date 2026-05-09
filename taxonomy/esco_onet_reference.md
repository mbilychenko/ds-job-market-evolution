# ESCO & O*NET Skill Reference — Data Science Occupations

**Purpose:** Reference document grounding Pass 2 (Opus normalization) of the skill extraction pipeline.  
When Opus assigns canonical skill names, prefer terms that appear in this document.

**Sources:**
- ESCO v1.2 (May 2024) — European Skills/Competencies/Qualifications and Occupations
- O*NET 29.0 (2024) — US Occupational Information Network

**Retrieved:** 2026-05-07  
**ESCO crosswalk note:** "Machine Learning Engineer" and "AI Engineer" have no dedicated ESCO occupation code.
Both map approximately to Data Scientist + ICT Application Developer + ICT System Developer.
O*NET similarly has no dedicated SOC for these roles; they map to 15-2051.00 and 15-1221.00.

---

## Occupation Mapping

| Our Canonical Role | ESCO Occupation(s) | ESCO URI | O*NET SOC Code(s) |
|---|---|---|---|
| Data Scientist | Data Scientist | `258e46f9-0075-4a2e-adae-1ff0477e0f30` | 15-2051.00 |
| Data Analyst | Data Analyst | `d3edb8f8-3a06-47a0-8fb9-9b212c006aa2` | 15-2031.00, 15-1242.00 |
| Data Engineer | Database Designer, ICT System Developer | `8d9ec84d-cf2d-4179-87bc-335cda54a427`, `a7c1d23d-aeca-4bee-9a08-5993ed98b135` | 15-1242.00, 15-1252.00 |
| Research Scientist | Data Scientist, Systems Analyst | `258e46f9-0075-4a2e-adae-1ff0477e0f30` | 15-1221.00 |
| ML Engineer | ICT Application Developer, ICT System Developer, Data Scientist | `bd272aee-adc9-4a06-a15c-a73b4b4a46a7`, `a7c1d23d-aeca-4bee-9a08-5993ed98b135` | 15-2051.00, 15-1221.00, 15-1252.00 |
| AI Engineer | No dedicated ESCO occupation | — | No dedicated SOC code |

---

## Skills by Role

---

### Data Scientist

**ESCO — Essential Skills**
- Find and interpret rich data sources
- Manage large amounts of data
- Merge data sources
- Data cleansing and quality implementation
- Database design and management
- Mathematical modelling and statistical analysis
- Data visualisation and presentation
- Research methodology and scientific integrity
- Processing and analysis using specialised techniques
- Open source software operation
- Query language proficiency
- Building recommendation systems

**ESCO — Essential Knowledge**
- Data engineering
- Data mining
- Data ethics
- Data models
- Visualisation software
- Statistical modelling techniques
- Quantitative analysis
- Empirical methods

**ESCO — Optional Skills & Knowledge**
- Business analytics and intelligence
- Cloud database design
- Data architecture management
- Image recognition
- Social network analysis
- Hadoop
- SPARQL
- Business intelligence platforms
- Cloud technologies
- Web analytics

**O*NET (15-2051.00) — Technology Skills (Hot Technologies)**
- Python
- R
- Java
- Scala
- Perl
- Go
- Ruby
- JavaScript
- SAS
- TensorFlow
- MATLAB
- IBM SPSS Statistics
- PostgreSQL
- MongoDB
- Apache Cassandra
- Apache Hive
- Elasticsearch
- Snowflake
- Amazon Redshift
- NoSQL
- Teradata Database
- Apache Pig
- AWS (EC2, S3, SageMaker)
- Microsoft Azure
- Google Cloud
- Docker
- Kubernetes
- Tableau
- Microsoft Power BI
- Alteryx
- Apache Spark
- Git / GitHub
- Apache Kafka
- Jenkins CI
- Apache Airflow
- JIRA
- Hadoop
- NumPy
- pandas
- PySpark

**O*NET (15-2051.00) — Core Skills**
- Statistical analysis and data manipulation
- Data mining and modelling techniques
- Machine learning application
- Natural language processing
- Feature selection algorithms
- Data visualisation and reporting
- Mathematical problem-solving
- Data quality assessment and preparation
- Model development, testing, and validation
- Trend identification and pattern analysis
- Business intelligence analysis

---

### Data Analyst

**ESCO — Essential Skills**
- Analyse big data
- Perform data cleansing
- Use databases
- Apply statistical analysis techniques
- Execute analytical mathematical calculations
- Manage data
- Collect ICT data
- Integrate ICT data
- Define data quality criteria
- Implement data quality processes
- Perform data mining
- Use data processing techniques

**ESCO — Essential Knowledge**
- Business analytics
- Business intelligence
- Data science
- Data models
- Data mining
- Data quality assessment
- Statistics
- Digital data processing
- Query languages
- Data visualisation software
- Data ethics
- Information confidentiality

**ESCO — Optional Skills & Knowledge**
- Create data models
- Deliver visual presentation of data
- Make data-driven decisions
- Manage cloud data and storage
- Report analysis results
- Hadoop
- Cloud technologies
- SPARQL
- XQuery
- Web analytics
- Social network analysis
- Statistical modelling techniques

**O*NET (15-2031.00) — Technology Skills**
- IBM SPSS Statistics
- ILOG OPL-CPLEX
- Minitab
- MATLAB
- Microsoft Power BI
- Oracle Business Intelligence
- Tableau
- Microsoft Excel
- SQL
- MySQL
- Microsoft SQL Server
- Python
- R
- C

**O*NET (15-2031.00) — Core Skills**
- Mathematics
- Complex problem solving
- Critical thinking
- Deductive and inductive reasoning
- Number facility

---

### Data Engineer

**ESCO (Database Designer) — Essential Skills**
- Analyse business requirements
- Design database schema
- Create database diagrams
- Perform data analysis
- Migrate existing data
- Operate relational database management system
- Apply ICT systems theory
- Create software design
- Define technical requirements
- Manage standards for data exchange
- Write documentation
- Implement automated migration approaches

**ESCO (Database Designer) — Essential Knowledge**
- Database management systems
- Query languages
- Systems development life-cycle
- Database development tools
- Information structure
- Security legislation relevant to ICT

**ESCO (Database Designer) — Optional Skills & Knowledge**
- Cloud-based database design
- SQL Server
- Oracle
- PostgreSQL
- MySQL
- MarkLogic
- Teradata Database
- Data engineering
- Data science

**ESCO (ICT System Developer) — Essential Skills**
- Analyse software specifications
- Debug software
- Develop automated migration methods
- Solve ICT system problems
- Use software design patterns
- Use software libraries

**ESCO (ICT System Developer) — Optional Skills**
- Automate cloud tasks
- Design cloud architecture
- Develop with cloud services
- Integrate system components
- Monitor system performance
- Plan migration to cloud
- Use object-oriented programming
- Use query languages

**O*NET (15-1242.00) — Technology Skills (Hot Technologies)**
- Oracle
- SQL Server
- PostgreSQL
- MongoDB
- Amazon DynamoDB
- Apache Cassandra
- Elasticsearch
- NoSQL
- Oracle PL/SQL
- Teradata Database
- Redis
- Apache Spark
- Microsoft Power BI
- Tableau
- AWS CloudFormation
- Microsoft Azure Data Factory
- Docker
- GitHub
- Red Hat OpenShift
- Spring Boot
- Chef
- Puppet
- Red Hat Ansible

---

### Research Scientist

**ESCO — see Data Scientist above (same occupation mapping)**

**O*NET (15-1221.00) — Hot Technologies (% of job postings)**
- Python (65%)
- Amazon Web Services (34%)
- Microsoft Azure (22%)
- PyTorch (27%)
- TensorFlow (25%)
- Apache Spark (12%)
- R (11%)
- Kubernetes (18%)
- Docker (15%)
- C++ (16%)
- Java (16%)
- Go (9%)
- SQL (19%)
- NoSQL (5%)
- PostgreSQL (3%)
- MongoDB (2%)
- Git / GitHub (8%)
- Ansible (6%)
- Jenkins CI (6%)
- Tableau (3%)
- Microsoft Power BI (3%)
- Bash (5%)
- JavaScript (6%)
- C (6%)
- Scikit-learn
- Apache Kafka
- OpenAI ChatGPT
- Hugging Face

**O*NET (15-1221.00) — Core Skills**
- Complex problem solving
- Critical thinking
- Programming
- Systems analysis
- Mathematics
- Research methodology
- AI/ML algorithm design
- Human-computer interaction
- Virtual reality
- Robotics

---

### ML Engineer

*No dedicated ESCO or O*NET occupation. Skills are a union of Data Scientist + ICT Application/System Developer.*

**ESCO (ICT Application Developer) — Essential Skills**
- Analyse software specifications
- Create flowchart diagram
- Debug software
- Develop software prototype
- Identify customer requirements
- Manage business knowledge
- Propose ICT solutions to business problems
- Use software design patterns
- Use software libraries
- Utilise computer-aided software engineering tools

**ESCO (ICT Application Developer) — Optional Knowledge**
- Python
- Java
- JavaScript
- C++
- SQL
- Object-oriented programming
- Functional programming
- Logic programming
- Concurrent programming

**O*NET — see Data Scientist (15-2051.00) and Research Scientist (15-1221.00) above**

Additional skills commonly associated with ML Engineer (from O*NET hot technologies):
- MLflow
- Kubeflow
- Apache Airflow
- Feature stores
- CI/CD pipelines
- Model monitoring
- Model serving (TorchServe, TensorFlow Serving)
- A/B testing frameworks

---

### AI Engineer

*No dedicated ESCO or O*NET occupation as of 2024.*

**Skills are a union of Data Scientist + ICT Application Developer + emerging LLM-era skills.**

Core skills from O*NET research scientist and data scientist profiles plus industry consensus:
- Python
- PyTorch / TensorFlow
- Hugging Face Transformers
- Large language models (LLMs)
- Retrieval-augmented generation (RAG)
- Vector databases (Pinecone, Weaviate, Chroma, pgvector)
- Embeddings
- Prompt engineering
- LLM fine-tuning (LoRA, QLoRA, PEFT)
- LLM evaluation
- LangChain / LlamaIndex
- OpenAI API / Anthropic API
- Agents / agentic workflows
- AWS / Azure / GCP
- Docker / Kubernetes
- Git / GitHub

---

## Cross-Role Skills (appear in 4+ of 6 roles)

These skills should be treated as high-confidence canonical terms during normalization:

**Programming Languages**
- Python, R, SQL, Java, Scala, C++, JavaScript, Go, Bash

**Cloud Platforms**
- AWS (Amazon Web Services), Microsoft Azure, Google Cloud Platform (GCP)

**Databases**
- PostgreSQL, MySQL, MongoDB, Oracle, SQL Server, Elasticsearch, Redis, Teradata,
  Apache Cassandra, Amazon Redshift, Snowflake, NoSQL, Amazon DynamoDB

**Data Processing**
- Apache Spark, Apache Kafka, Apache Airflow, Apache Hadoop, PySpark, pandas

**ML Frameworks**
- TensorFlow, PyTorch, Scikit-learn

**MLOps / Infrastructure**
- Docker, Kubernetes, Git / GitHub, Jenkins CI

**Visualisation / BI**
- Tableau, Microsoft Power BI, Matplotlib

**Statistics / Analysis**
- Statistical analysis, Data mining, Data modelling, Machine learning,
  Natural language processing, Data visualisation, Data quality

---

## Skills With No Equivalent in ESCO (LLM-era, post-2022)

These terms will not appear in ESCO occupation profiles. They should still be treated as valid
canonical skills during normalization — they reflect post-2022 industry demand not yet codified
in official taxonomies.

- Retrieval-Augmented Generation (RAG)
- Vector databases (Pinecone, Weaviate, Chroma, Qdrant, Milvus, pgvector)
- LLM fine-tuning (LoRA, QLoRA, PEFT, RLHF)
- LLM evaluation / LLM Ops
- Prompt engineering
- AI agents / agentic workflows
- LangChain
- LlamaIndex
- Hugging Face (as a platform, beyond transformer models)
- vLLM
- Ollama
- OpenAI API
- Anthropic API
- Embeddings (as a standalone skill)
- Foundation models
- Multimodal models
- dbt (data build tool) — post-2020 data engineering
- Apache Iceberg / Delta Lake / Apache Hudi — modern table formats
- Feature stores (Feast, Tecton, Hopsworks)
