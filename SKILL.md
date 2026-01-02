---
name: iac-diagram-generator
description: Analyzes Infrastructure as Code files (Terraform, CloudFormation, Kubernetes, Docker Compose) and generates visual architecture diagrams. Use when analyzing infrastructure code, designing cloud architectures, or when the user requests architecture diagrams from IaC.
allowed-tools: Read, Bash, Glob, Grep
---

# IaC Architecture Diagram Generator

Analyzes Infrastructure as Code repositories and generates professional architecture diagrams using Nano Banana Pro. Supports Terraform, CloudFormation, Kubernetes, Docker Compose, Pulumi, and other common IaC formats.

## Core Philosophy

Infrastructure diagrams should accurately represent the logical architecture, resource relationships, and security boundaries defined in your IaC. This skill parses IaC files to extract resources, dependencies, and hierarchical structures, then generates diagrams that follow cloud architecture best practices.

## Workflow

When a user requests an architecture diagram from IaC files, follow these steps:

### Step 1: Discover IaC Files

Use Glob to identify IaC files in the target directory:

- **Terraform**: `*.tf`, `*.tfvars`
- **CloudFormation**: `*.yaml`, `*.yml`, `*.json`, `*.template`
- **Kubernetes**: `*.yaml`, `*.yml` (in manifests/, k8s/, kube/ directories)
- **Docker Compose**: `docker-compose.yaml`, `docker-compose.yml`
- **Pulumi**: `*.ts`, `*.py`, `*.go` (with Pulumi imports)
- **Azure ARM**: `*.json` (with ARM schema)
- **GCP Deployment Manager**: `*.yaml`, `*.jinja`, `*.py`

If no specific file is mentioned, search the current directory recursively.

### Step 2: Validate and Parse IaC Files

Run the appropriate parser script based on file type:

```bash
# Terraform
python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py terraform path/to/terraform/dir

# CloudFormation
python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py cloudformation path/to/template.yaml

# Kubernetes
python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py kubernetes path/to/manifests/

# Docker Compose
python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py docker-compose path/to/docker-compose.yaml
```

The parser will return a JSON structure containing:
- Resources (compute, networking, storage, security)
- Dependencies and relationships
- Hierarchical organization (VPCs, subnets, namespaces)
- Connection types (public internet, private, managed services)

### Step 3: Analyze the Resource Graph

Review the parsed structure to understand:
- **Hierarchy**: VPC > Availability Zones > Subnets > Resources
- **Resource Types**: Compute (EC2, Lambda), Networking (VPC, Load Balancers), Storage (S3, RDS), Security (IAM, Security Groups)
- **Dependencies**: Which resources depend on others (explicit and implicit)
- **Connections**: How resources communicate (HTTP, database connections, message queues)
- **Security Boundaries**: VPCs, subnets, security groups, network ACLs

### Step 4: Generate Nano Banana Pro Diagram Prompt

Create a detailed, structured prompt for Nano Banana Pro that describes the architecture diagram using natural language. Follow these guidelines:

#### Diagram Style Requirements

**Always specify**:
- "A professional cloud architecture diagram"
- "Clean, technical illustration style"
- "Use official AWS/Azure/GCP icon style for resources"
- "White or light gray background for clarity"

#### Hierarchical Organization

Describe the architecture from outermost to innermost layers:

1. **Cloud Provider / Region Level**
   - "The diagram shows an AWS architecture in the us-east-1 region"

2. **VPC / Virtual Network Level**
   - "A VPC labeled 'Production VPC (10.0.0.0/16)' contains all resources"
   - Use rectangular containers with dashed borders for VPCs

3. **Availability Zone / Subnet Level**
   - "Inside the VPC, there are three subnets arranged horizontally"
   - "A public subnet (10.0.1.0/24) on the left contains..."
   - "A private subnet (10.0.2.0/24) in the center contains..."
   - "A database subnet (10.0.3.0/24) on the right contains..."

4. **Resource Level**
   - Describe each resource with its icon type and label
   - "An Application Load Balancer icon labeled 'web-alb'"
   - "Three EC2 instance icons labeled 'web-1', 'web-2', 'web-3'"

#### Resource Representation

For each resource type, use appropriate descriptions:

**Compute**:
- "EC2 instance icons" (orange/brown server icons)
- "Lambda function icons" (orange lambda symbols)
- "Container icons for ECS tasks"

**Networking**:
- "Load balancer icon" (purple/blue distribution icon)
- "VPC router icon"
- "Internet gateway icon" (world/globe icon)
- "NAT gateway icon"

**Storage**:
- "S3 bucket icon" (green/orange bucket)
- "RDS database icon" (blue cylinder)
- "ElastiCache icon" (orange cache symbol)

**Security**:
- "Security group represented as a dotted border around resources"
- "IAM role icon" (orange key/badge)
- "WAF/firewall icon"

#### Connections and Data Flow

Describe how resources connect:

**Connection Types**:
- "A solid green arrow labeled 'HTTPS' connects the Internet Gateway to the Load Balancer"
- "Blue arrows labeled 'HTTP' connect the Load Balancer to the EC2 instances"
- "Red dashed arrows labeled 'PostgreSQL' connect the EC2 instances to the RDS database"

**Bidirectional Connections**:
- "A two-way arrow labeled 'VPC Peering' connects VPC-A to VPC-B"

**Network Boundaries**:
- "The public subnet has a path to the Internet Gateway"
- "The private subnet routes through a NAT Gateway for outbound access"
- "The database subnet has no direct internet access"

#### Labels and Text

**Critical - Specify Exact Text**:
- Enclose all labels in single quotes within the prompt
- "The VPC container is labeled 'Production VPC (10.0.0.0/16)'"
- "The Load Balancer is labeled 'web-alb'"
- "The database is labeled 'PostgreSQL RDS (db.t3.medium)'"

#### Layout and Composition

**Orientation**:
- "Left-to-right flow showing internet traffic entering from the left"
- "Top-to-bottom hierarchy with VPC at the top"

**Spacing and Clarity**:
- "Resources are evenly spaced with clear separation"
- "Connection arrows do not overlap"
- "Labels are positioned next to their resources without overlapping other elements"

### Step 5: Example Prompts for Different Architectures

**Three-Tier Web Application**:
```
A professional AWS cloud architecture diagram in a clean technical illustration style. The diagram uses official AWS icon styles on a white background.

The architecture shows a VPC labeled 'Production VPC (10.0.0.0/16)' represented as a large rectangular container with a dashed border.

Inside the VPC, there are three horizontal sections representing subnets:

In the 'Public Subnet (10.0.1.0/24)' on the left:
- An Internet Gateway icon at the far left edge
- An Application Load Balancer icon labeled 'web-alb' connected to the Internet Gateway

In the 'Private Subnet (10.0.2.0/24)' in the center:
- Three EC2 instance icons arranged vertically, labeled 'web-1', 'web-2', and 'web-3'
- These instances are grouped within a dotted border labeled 'web-sg security group'

In the 'Database Subnet (10.0.3.0/24)' on the right:
- An RDS database cylinder icon labeled 'PostgreSQL (db.t3.medium)'
- A dotted border labeled 'db-sg security group' surrounds it

Connections shown with arrows:
- A solid green arrow labeled 'HTTPS' connects the Internet Gateway to the Load Balancer
- Blue arrows labeled 'HTTP' connect the Load Balancer to each of the three EC2 instances
- Red dashed arrows labeled 'PostgreSQL:5432' connect each EC2 instance to the RDS database

The layout flows left to right showing the request path from internet to database. All resources are clearly labeled and evenly spaced. The style is professional and technical, suitable for architecture documentation.
```

**Microservices on Kubernetes**:
```
A professional Kubernetes architecture diagram in a clean technical illustration style on a white background.

The diagram shows a Kubernetes cluster represented by a large container labeled 'EKS Cluster (k8s-prod)'.

At the top:
- An Ingress Controller icon labeled 'nginx-ingress' with an arrow from 'Internet' entering from above

Inside the cluster, three namespace containers arranged horizontally:

The 'frontend' namespace (blue-tinted background) contains:
- Three Pod icons labeled 'web-app' arranged in a row
- A Service icon labeled 'frontend-svc' above the pods

The 'backend' namespace (green-tinted background) contains:
- Three Pod icons labeled 'api-server'
- A Service icon labeled 'api-svc'
- Two Pod icons labeled 'worker'

The 'data' namespace (orange-tinted background) contains:
- A StatefulSet icon labeled 'postgres'
- A PersistentVolumeClaim icon labeled 'db-storage'

Connections:
- A green arrow labeled 'HTTPS' from the Ingress to 'frontend-svc'
- Blue arrows labeled 'HTTP' from frontend pods to 'api-svc'
- Red arrows labeled 'gRPC' from api-server pods to worker pods
- Purple dashed arrows labeled 'PostgreSQL' from api-server pods to the postgres StatefulSet

External resources shown outside the cluster box:
- An S3 bucket icon labeled 'user-uploads' connected with a dashed line to worker pods
- An RDS icon labeled 'analytics-db' connected to api-server pods

The layout is organized with clear namespace boundaries and color-coded sections. Resources are evenly spaced with non-overlapping labels.
```

### Step 6: Generate the Diagram

After creating the enhanced prompt, generate the diagram:

```bash
python ~/.claude/skills/nanobanana/scripts/generate.py "ENHANCED_PROMPT_HERE"
```

The script will save the diagram as a timestamped PNG file in the current directory.

### Step 7: Provide Context

After generating the diagram, provide the user with:
1. The diagram filename and location
2. A summary of the architecture components
3. Any notable patterns or best practices observed
4. Suggestions for improvements if applicable

## Supported IaC Formats

### Terraform
- **Extensions**: `.tf`, `.tfvars`
- **Features**: Resource extraction, module resolution, variable handling
- **Dependencies**: Explicit (`depends_on`) and implicit (resource references)

### AWS CloudFormation
- **Extensions**: `.yaml`, `.yml`, `.json`, `.template`
- **Features**: Resource extraction, parameter resolution, intrinsic function parsing
- **Dependencies**: `DependsOn`, `Ref`, `GetAtt` references

### Kubernetes
- **Extensions**: `.yaml`, `.yml` (manifests, Helm templates)
- **Features**: Resource extraction, label selectors, namespace organization
- **Dependencies**: Service selectors, ConfigMap/Secret references, ownerReferences

### Docker Compose
- **Extensions**: `docker-compose.yaml`, `docker-compose.yml`
- **Features**: Service extraction, network topology, volume mappings
- **Dependencies**: `depends_on`, network membership, volume sharing

### Pulumi
- **Extensions**: `.ts`, `.py`, `.go`
- **Features**: Basic resource extraction from code analysis
- **Note**: Requires language-specific AST parsing

## Best Practices

### DO:
- Start with the highest level of hierarchy (region/VPC) and work down to individual resources
- Use official cloud provider icon terminology in prompts
- Specify exact text for all labels in single quotes
- Describe connection types and protocols clearly
- Group resources by security boundaries (VPCs, subnets, security groups)
- Use color coding for different resource types or environments
- Include CIDR blocks for networks and subnets
- Show directionality of connections (arrows pointing from source to destination)

### DON'T:
- Mix different cloud providers in the same diagram unless it's a multi-cloud architecture
- Omit security boundaries and network segmentation
- Create overly complex diagrams with too many resources (split into multiple diagrams if needed)
- Forget to label connections with protocol and port information
- Use vague descriptions like "some servers" (be specific about resource types and names)

## Common Architecture Patterns

### Three-Tier Web Application
- Public subnet: Load balancers, NAT gateways
- Private subnet: Application servers, workers
- Database subnet: RDS, ElastiCache (no direct internet access)

### Microservices
- API Gateway / Ingress at the edge
- Service mesh for inter-service communication
- Separate namespaces or VPCs per service domain
- Shared data stores and message queues

### Serverless
- API Gateway triggering Lambda functions
- Lambda functions accessing DynamoDB, S3
- EventBridge or SQS for async processing
- CloudFront for content delivery

## Setup Requirements

### Required Python Packages

```bash
pip install pyyaml google-genai
```

### Environment Variables

```bash
# Gemini API key for Nano Banana Pro
export GEMINI_API_KEY="your-api-key-here"
```

Get your API key at: https://aistudio.google.com/apikey

### Optional Tools

For enhanced Terraform parsing:
```bash
pip install tfparse
```

For CloudFormation validation:
```bash
pip install cfn-lint
```

## Error Handling

The parser handles:
- Missing or invalid IaC files
- Unsupported IaC formats
- Syntax errors in IaC (reports to user)
- Missing environment variables
- File read permissions

All errors include clear messages for troubleshooting.

## Examples

### Example 1: Terraform Directory

**User Request**: "Generate an architecture diagram from my Terraform code"

**Steps**:
1. Use Glob to find `.tf` files in current directory
2. Run: `python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py terraform .`
3. Analyze the JSON output to understand the architecture
4. Create enhanced Nano Banana Pro prompt describing the AWS resources, VPC structure, and connections
5. Generate diagram: `python ~/.claude/skills/nanobanana/scripts/generate.py "PROMPT"`
6. Report diagram location and summary

### Example 2: CloudFormation Template

**User Request**: "Show me what this CloudFormation template deploys"

**Steps**:
1. Identify the template file
2. Run: `python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py cloudformation template.yaml`
3. Extract resources and dependencies from JSON
4. Create detailed prompt showing resource hierarchy and connections
5. Generate diagram
6. Explain the architecture and resource relationships

### Example 3: Kubernetes Manifests

**User Request**: "Diagram our Kubernetes application"

**Steps**:
1. Find YAML manifests in k8s/ or manifests/ directory
2. Run: `python ~/.claude/skills/iac-diagram-generator/scripts/parse_iac.py kubernetes k8s/`
3. Identify Deployments, Services, Ingresses, and their relationships
4. Create prompt showing namespace organization and service communication
5. Generate diagram
6. Provide insights on the microservices architecture
