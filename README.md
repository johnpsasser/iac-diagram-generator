# IaC Diagram Generator

Generate professional cloud architecture diagrams from Infrastructure as Code files. Works with Terraform, CloudFormation, Kubernetes, Docker Compose, and more.

## Quick Install

```bash
git clone https://github.com/johnpsasser/iac-diagram-generator.git
cd iac-diagram-generator
./install.sh
```

## Requirements

- Claude Code CLI
- [nanobanana skill](https://github.com/johnpsasser/nanobanana) (for diagram generation)
- Python 3.7+
- Gemini API key (get one at [ai.google.dev](https://aistudio.google.com/apikey))

## Usage

After installation, just ask Claude Code to analyze your infrastructure:

```bash
# From a directory with Terraform files
"Generate an architecture diagram from my Terraform code"

# From a specific CloudFormation template
"Show me what this CloudFormation template deploys"

# From Kubernetes manifests
"Diagram our Kubernetes application in the k8s/ directory"

# From Docker Compose
"Visualize my docker-compose.yaml services"
```

Claude Code will automatically:
1. Detect and parse your IaC files
2. Extract resources, relationships, and network topology
3. Generate a detailed architecture diagram using AI
4. Save the diagram as a PNG in your current directory

## Supported Formats

### Terraform
- `.tf` and `.tfvars` files
- Extracts resources, modules, and variables
- Identifies provider-specific resources (AWS, Azure, GCP)

### CloudFormation
- `.yaml`, `.yml`, `.json`, `.template` files
- Parses resources with intrinsic functions (Ref, GetAtt)
- Extracts explicit and implicit dependencies

### Kubernetes
- Manifest files (`.yaml`, `.yml`)
- Helm chart templates
- Identifies Deployments, Services, Ingresses, and relationships

### Docker Compose
- `docker-compose.yaml` files
- Extracts services, networks, volumes
- Maps service dependencies and connections

## How It Works

1. **Parse**: The skill scans your directory for IaC files and parses them into a structured representation
2. **Analyze**: Extracts resource hierarchies (VPC > Subnets > Resources), dependencies, and connection types
3. **Generate**: Creates an optimized prompt for Nano Banana Pro describing the architecture in detail
4. **Render**: Generates a professional diagram using AI image generation

## Example Outputs

### Three-Tier Web Application
From a CloudFormation template defining a VPC, load balancer, EC2 instances, and RDS database, the skill generates a diagram showing:
- VPC with labeled CIDR blocks
- Public, private, and database subnets
- Internet gateway and load balancer
- Application servers grouped by security group
- Database with security boundaries
- Connection arrows labeled with protocols (HTTPS, HTTP, PostgreSQL)

### Microservices on Kubernetes
From Kubernetes manifests, generates diagrams showing:
- Namespace organization
- Services and their pod selectors
- Ingress routing rules
- External dependencies (S3, RDS)
- Inter-service communication

## Manual Installation

If you prefer manual setup:

```bash
# 1. Copy skill files
mkdir -p ~/.claude/skills/iac-diagram-generator
cp -r SKILL.md scripts ~/.claude/skills/iac-diagram-generator/

# 2. Install Python dependencies
pip install pyyaml

# 3. Set your Gemini API key
export GEMINI_API_KEY='your-key-here'

# 4. Install nanobanana skill
git clone https://github.com/johnpsasser/nanobanana.git
cd nanobanana && ./install.sh
```

## Parsing Details

### Terraform
Uses regex-based HCL parsing to extract resource blocks. For production use with complex Terraform (modules, dynamic blocks, count/for_each), consider using `tfparse` or the official HCL parser.

### CloudFormation
Handles CloudFormation intrinsic functions (!Ref, !GetAtt, !Sub, etc.) and extracts both explicit (DependsOn) and implicit (Ref references) dependencies.

### Kubernetes
Parses multi-document YAML files and extracts label-based relationships between Services, Deployments, and Pods.

### Docker Compose
Extracts service definitions, dependency chains (depends_on), network membership, and volume mounts.

## Troubleshooting

**Parser errors**:
- Ensure IaC files are syntactically valid
- For Terraform, check that resource blocks follow standard format
- For CloudFormation, validate against AWS schema

**No diagram generated**:
- Verify nanobanana skill is installed
- Check GEMINI_API_KEY environment variable is set
- Review Claude Code output for error messages

**Incomplete diagrams**:
- Parser uses simplified extraction for complex IaC features
- Consider manually verifying resource relationships
- Large architectures may benefit from splitting into multiple diagrams

## Architecture

The skill consists of:

- `SKILL.md` - Main skill definition with diagram generation guidelines
- `scripts/parse_iac.py` - Python parser for multiple IaC formats
- `install.sh` - One-click installer script

The parser outputs JSON with resource definitions and dependencies. Claude Code uses this to create detailed prompts for Nano Banana Pro, following architecture diagram best practices (hierarchical organization, proper labeling, connection types, security boundaries).

## Limitations

- Terraform parsing is regex-based and may not handle complex HCL features (nested modules, complex expressions)
- Pulumi support requires static analysis of code (limited compared to declarative formats)
- Very large infrastructures (100+ resources) may produce cluttered diagrams
- Diagram accuracy depends on IaC completeness and AI interpretation

## Contributing

Contributions welcome. Focus areas:
- Enhanced Terraform HCL parsing (possibly integrating tfparse)
- Pulumi language-specific parsers
- Azure ARM template support
- GCP Deployment Manager support
- Additional diagram layout optimizations

## License

MIT. Do whatever you want with it.

## Credits

Built for Claude Code. Uses Nano Banana Pro (Gemini 3 Pro Image) for diagram generation.

See also: [nanobanana](https://github.com/johnpsasser/nanobanana)
