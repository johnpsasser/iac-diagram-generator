#!/usr/bin/env python3
"""
IaC Parser
Parses Infrastructure as Code files and extracts resource information.
Supports: Terraform, CloudFormation, Kubernetes, Docker Compose
Accepts: Local paths or GitHub repository URLs
"""

import os
import sys
import json
import glob as file_glob
import tempfile
import shutil
import subprocess
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is not installed.")
    print("Please install it with: pip install pyyaml")
    sys.exit(1)


def is_github_url(path):
    """Check if the path is a GitHub URL."""
    github_patterns = [
        r'^https?://github\.com/[\w\-\.]+/[\w\-\.]+',
        r'^git@github\.com:[\w\-\.]+/[\w\-\.]+',
        r'^github\.com/[\w\-\.]+/[\w\-\.]+',
    ]
    for pattern in github_patterns:
        if re.match(pattern, path):
            return True
    return False


def normalize_github_url(url):
    """Normalize GitHub URL to HTTPS clone format."""
    # Remove trailing slashes and .git
    url = url.rstrip('/').rstrip('.git')

    # Handle different formats
    if url.startswith('git@github.com:'):
        # git@github.com:user/repo -> https://github.com/user/repo
        url = url.replace('git@github.com:', 'https://github.com/')
    elif url.startswith('github.com/'):
        # github.com/user/repo -> https://github.com/user/repo
        url = 'https://' + url
    elif not url.startswith('http'):
        url = 'https://' + url

    return url + '.git'


def clone_repository(url, subpath=None):
    """
    Clone a GitHub repository to a temporary directory.

    Args:
        url: GitHub repository URL
        subpath: Optional subdirectory within the repo to use

    Returns:
        tuple: (temp_dir, target_path) where target_path is the directory to parse
    """
    normalized_url = normalize_github_url(url)

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='iac_parser_')

    print(f"Cloning repository: {normalized_url}")
    print(f"  Temp directory: {temp_dir}")

    try:
        # Clone with depth=1 for speed (we only need latest files)
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', normalized_url, temp_dir],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        if result.returncode != 0:
            print(f"ERROR: Git clone failed: {result.stderr}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, None

        print("  Clone successful!")

        # Determine target path
        target_path = temp_dir
        if subpath:
            target_path = os.path.join(temp_dir, subpath.lstrip('/'))
            if not os.path.exists(target_path):
                print(f"ERROR: Subpath does not exist in repo: {subpath}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None, None

        return temp_dir, target_path

    except subprocess.TimeoutExpired:
        print("ERROR: Git clone timed out (120s)")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, None
    except FileNotFoundError:
        print("ERROR: Git is not installed or not in PATH")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, None
    except Exception as e:
        print(f"ERROR: Failed to clone repository: {str(e)}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, None


def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory."""
    if temp_dir and os.path.exists(temp_dir):
        print(f"\nCleaning up temp directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


# CloudFormation YAML intrinsic function constructors
def cloudformation_constructor(loader, tag_suffix, node):
    """Generic constructor for CloudFormation intrinsic functions."""
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node)}
    else:
        return {tag_suffix: None}


# Register CloudFormation intrinsic functions
yaml.add_multi_constructor('!', cloudformation_constructor, Loader=yaml.SafeLoader)


def parse_terraform(path):
    """
    Parse Terraform files (.tf) to extract resources.

    Note: This is a simplified parser that handles basic HCL syntax.
    For production use, consider using tfparse or the official HCL parser.
    """
    print(f"Parsing Terraform files in: {path}")

    # Find all .tf files
    if os.path.isfile(path):
        tf_files = [path]
    else:
        tf_files = file_glob.glob(os.path.join(path, "**/*.tf"), recursive=True)

    if not tf_files:
        return {"error": "No Terraform files found", "resources": [], "dependencies": {}}

    resources = []
    variables = {}
    modules = []

    for tf_file in tf_files:
        print(f"  Reading: {tf_file}")
        try:
            with open(tf_file, 'r') as f:
                content = f.read()

            # Basic resource extraction (simplified - real HCL parsing is complex)
            # Look for resource blocks: resource "type" "name" { ... }
            import re

            # Extract resources
            resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s+\{'
            for match in re.finditer(resource_pattern, content):
                resource_type = match.group(1)
                resource_name = match.group(2)
                resources.append({
                    "type": resource_type,
                    "name": resource_name,
                    "full_name": f"{resource_type}.{resource_name}",
                    "file": tf_file,
                    "provider": resource_type.split("_")[0] if "_" in resource_type else "unknown"
                })

            # Extract variables
            var_pattern = r'variable\s+"([^"]+)"\s+\{'
            for match in re.finditer(var_pattern, content):
                var_name = match.group(1)
                variables[var_name] = {"name": var_name, "file": tf_file}

            # Extract modules
            module_pattern = r'module\s+"([^"]+)"\s+\{'
            for match in re.finditer(module_pattern, content):
                module_name = match.group(1)
                modules.append({"name": module_name, "file": tf_file})

        except Exception as e:
            print(f"  Warning: Error reading {tf_file}: {e}")
            continue

    return {
        "format": "terraform",
        "resources": resources,
        "variables": variables,
        "modules": modules,
        "total_resources": len(resources),
        "dependencies": extract_terraform_dependencies(resources)
    }


def extract_terraform_dependencies(resources):
    """Extract basic dependency information from Terraform resources."""
    # Simplified - real dependency extraction requires parsing resource attributes
    dependencies = {}

    # Group resources by type for basic relationship inference
    resource_types = {}
    for resource in resources:
        r_type = resource["type"]
        if r_type not in resource_types:
            resource_types[r_type] = []
        resource_types[r_type].append(resource["name"])

    # Infer common patterns
    for resource in resources:
        deps = []
        r_type = resource["type"]

        # Common AWS patterns
        if r_type == "aws_instance":
            # Instances typically depend on VPC, subnet, security group
            if "aws_vpc" in resource_types:
                deps.extend([f"aws_vpc.{name}" for name in resource_types["aws_vpc"]])
            if "aws_subnet" in resource_types:
                deps.extend([f"aws_subnet.{name}" for name in resource_types["aws_subnet"]])
            if "aws_security_group" in resource_types:
                deps.extend([f"aws_security_group.{name}" for name in resource_types["aws_security_group"]])

        elif r_type == "aws_elb" or r_type == "aws_lb":
            # Load balancers depend on subnets and security groups
            if "aws_subnet" in resource_types:
                deps.extend([f"aws_subnet.{name}" for name in resource_types["aws_subnet"]])

        elif r_type == "aws_db_instance":
            # RDS depends on subnet groups and security groups
            if "aws_db_subnet_group" in resource_types:
                deps.extend([f"aws_db_subnet_group.{name}" for name in resource_types["aws_db_subnet_group"]])

        dependencies[resource["full_name"]] = deps

    return dependencies


def parse_cloudformation(path):
    """Parse CloudFormation template (YAML or JSON)."""
    print(f"Parsing CloudFormation template: {path}")

    try:
        with open(path, 'r') as f:
            if path.endswith('.json'):
                template = json.load(f)
            else:
                template = yaml.safe_load(f)

        resources = []
        parameters = template.get('Parameters', {})
        outputs = template.get('Outputs', {})
        cfn_resources = template.get('Resources', {})

        for logical_id, resource in cfn_resources.items():
            resource_type = resource.get('Type', 'Unknown')
            properties = resource.get('Properties', {})

            # Extract provider from type (AWS::EC2::Instance -> AWS)
            provider_parts = resource_type.split('::')
            provider = provider_parts[0] if len(provider_parts) > 0 else 'Unknown'
            service = provider_parts[1] if len(provider_parts) > 1 else 'Unknown'

            resources.append({
                "logical_id": logical_id,
                "type": resource_type,
                "provider": provider,
                "service": service,
                "properties": properties,
                "depends_on": resource.get('DependsOn', [])
            })

        # Extract dependencies from Ref and GetAtt
        dependencies = {}
        for logical_id, resource in cfn_resources.items():
            deps = set()

            # Explicit dependencies
            depends_on = resource.get('DependsOn', [])
            if isinstance(depends_on, str):
                deps.add(depends_on)
            elif isinstance(depends_on, list):
                deps.update(depends_on)

            # Implicit dependencies from references
            refs = extract_cloudformation_refs(resource)
            deps.update(refs)

            dependencies[logical_id] = list(deps)

        return {
            "format": "cloudformation",
            "resources": resources,
            "parameters": list(parameters.keys()),
            "outputs": list(outputs.keys()),
            "total_resources": len(resources),
            "dependencies": dependencies
        }

    except Exception as e:
        return {"error": f"Failed to parse CloudFormation template: {str(e)}"}


def extract_cloudformation_refs(obj, refs=None):
    """Recursively extract Ref and GetAtt references from CloudFormation template."""
    if refs is None:
        refs = set()

    if isinstance(obj, dict):
        if 'Ref' in obj:
            ref_value = obj['Ref']
            # Filter out pseudo-parameters
            if not ref_value.startswith('AWS::'):
                refs.add(ref_value)
        elif 'Fn::GetAtt' in obj:
            get_att = obj['Fn::GetAtt']
            if isinstance(get_att, list) and len(get_att) > 0:
                refs.add(get_att[0])
            elif isinstance(get_att, str):
                # Format: "LogicalId.AttributeName"
                refs.add(get_att.split('.')[0])
        else:
            for value in obj.values():
                extract_cloudformation_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            extract_cloudformation_refs(item, refs)

    return refs


def parse_kubernetes(path):
    """Parse Kubernetes manifests (YAML)."""
    print(f"Parsing Kubernetes manifests in: {path}")

    # Find all YAML files
    if os.path.isfile(path):
        yaml_files = [path]
    else:
        yaml_files = file_glob.glob(os.path.join(path, "**/*.yaml"), recursive=True)
        yaml_files.extend(file_glob.glob(os.path.join(path, "**/*.yml"), recursive=True))

    if not yaml_files:
        return {"error": "No Kubernetes manifest files found", "resources": []}

    resources = []

    for yaml_file in yaml_files:
        print(f"  Reading: {yaml_file}")
        try:
            with open(yaml_file, 'r') as f:
                # Handle multi-document YAML (--- separator)
                documents = yaml.safe_load_all(f)

                for doc in documents:
                    if doc is None or not isinstance(doc, dict):
                        continue

                    kind = doc.get('kind', 'Unknown')
                    api_version = doc.get('apiVersion', 'Unknown')
                    metadata = doc.get('metadata', {})
                    spec = doc.get('spec', {})

                    name = metadata.get('name', 'unnamed')
                    namespace = metadata.get('namespace', 'default')
                    labels = metadata.get('labels', {})

                    resource = {
                        "kind": kind,
                        "apiVersion": api_version,
                        "name": name,
                        "namespace": namespace,
                        "labels": labels,
                        "file": yaml_file
                    }

                    # Extract specific fields based on kind
                    if kind == 'Service':
                        resource["selector"] = spec.get('selector', {})
                        resource["ports"] = spec.get('ports', [])
                    elif kind == 'Deployment':
                        resource["replicas"] = spec.get('replicas', 1)
                        resource["selector"] = spec.get('selector', {})
                    elif kind == 'Ingress':
                        resource["rules"] = spec.get('rules', [])

                    resources.append(resource)

        except Exception as e:
            print(f"  Warning: Error reading {yaml_file}: {e}")
            continue

    # Extract relationships
    relationships = extract_kubernetes_relationships(resources)

    return {
        "format": "kubernetes",
        "resources": resources,
        "total_resources": len(resources),
        "namespaces": list(set(r["namespace"] for r in resources)),
        "relationships": relationships
    }


def extract_kubernetes_relationships(resources):
    """Extract relationships between Kubernetes resources."""
    relationships = []

    for resource in resources:
        kind = resource["kind"]
        name = resource["name"]
        namespace = resource["namespace"]

        if kind == "Service":
            # Service selects Pods via label selector
            selector = resource.get("selector", {})
            if selector:
                relationships.append({
                    "from": f"Service/{name}",
                    "to": f"Pods with labels {selector}",
                    "type": "selects",
                    "namespace": namespace
                })

        elif kind == "Deployment":
            # Deployment creates ReplicaSet creates Pods
            relationships.append({
                "from": f"Deployment/{name}",
                "to": f"ReplicaSet/{name}-*",
                "type": "creates",
                "namespace": namespace
            })

        elif kind == "Ingress":
            # Ingress routes to Services
            rules = resource.get("rules", [])
            for rule in rules:
                http = rule.get("http", {})
                for path in http.get("paths", []):
                    backend = path.get("backend", {})
                    service_name = None

                    # Handle different API versions
                    if "serviceName" in backend:
                        service_name = backend["serviceName"]
                    elif "service" in backend:
                        service_name = backend["service"].get("name")

                    if service_name:
                        relationships.append({
                            "from": f"Ingress/{name}",
                            "to": f"Service/{service_name}",
                            "type": "routes",
                            "namespace": namespace
                        })

    return relationships


def parse_docker_compose(path):
    """Parse Docker Compose file (YAML)."""
    print(f"Parsing Docker Compose file: {path}")

    try:
        with open(path, 'r') as f:
            compose = yaml.safe_load(f)

        services = compose.get('services', {})
        networks = compose.get('networks', {})
        volumes = compose.get('volumes', {})

        service_list = []
        dependencies = {}

        for service_name, service_config in services.items():
            depends_on = service_config.get('depends_on', [])

            # depends_on can be a list or a dict
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())

            service_networks = service_config.get('networks', [])
            if isinstance(service_networks, dict):
                service_networks = list(service_networks.keys())

            service_volumes = service_config.get('volumes', [])

            service_list.append({
                "name": service_name,
                "image": service_config.get('image'),
                "build": service_config.get('build'),
                "ports": service_config.get('ports', []),
                "environment": service_config.get('environment', {}),
                "networks": service_networks,
                "volumes": service_volumes
            })

            dependencies[service_name] = {
                "depends_on": depends_on,
                "networks": service_networks
            }

        return {
            "format": "docker-compose",
            "services": service_list,
            "networks": list(networks.keys()),
            "volumes": list(volumes.keys()),
            "total_services": len(service_list),
            "dependencies": dependencies
        }

    except Exception as e:
        return {"error": f"Failed to parse Docker Compose file: {str(e)}"}


def extract_github_subpath(url):
    """
    Extract subpath from GitHub URL if specified.

    Examples:
        https://github.com/user/repo/tree/main/terraform -> ('https://github.com/user/repo', 'terraform')
        https://github.com/user/repo -> ('https://github.com/user/repo', None)
    """
    # Match URLs with /tree/branch/path or /blob/branch/path
    match = re.match(r'^(https?://github\.com/[\w\-\.]+/[\w\-\.]+)(?:/(?:tree|blob)/[^/]+)?(?:/(.+))?$', url)
    if match:
        base_url = match.group(1)
        subpath = match.group(2)
        return base_url, subpath
    return url, None


def main():
    """Main entry point for the IaC parser."""
    if len(sys.argv) < 3:
        print("ERROR: Missing required arguments.")
        print("\nUsage: python parse_iac.py <format> <path>")
        print("\nSupported formats:")
        print("  terraform       - Parse Terraform .tf files")
        print("  cloudformation  - Parse CloudFormation templates (.yaml, .json)")
        print("  kubernetes      - Parse Kubernetes manifests (.yaml)")
        print("  docker-compose  - Parse Docker Compose files")
        print("\nPath can be:")
        print("  - Local file or directory")
        print("  - GitHub repository URL (will be cloned automatically)")
        print("\nExamples:")
        print("  python parse_iac.py terraform ./infrastructure")
        print("  python parse_iac.py cloudformation template.yaml")
        print("  python parse_iac.py kubernetes ./k8s")
        print("  python parse_iac.py docker-compose docker-compose.yaml")
        print("\n  # GitHub repositories:")
        print("  python parse_iac.py terraform https://github.com/user/repo")
        print("  python parse_iac.py terraform https://github.com/user/repo/tree/main/terraform")
        print("  python parse_iac.py cloudformation github.com/user/repo")
        sys.exit(1)

    iac_format = sys.argv[1].lower()
    path = sys.argv[2]

    temp_dir = None  # Track temp directory for cleanup

    # Check if path is a GitHub URL
    if is_github_url(path):
        # Extract base URL and optional subpath
        base_url, subpath = extract_github_subpath(path)

        # Clone the repository
        temp_dir, path = clone_repository(base_url, subpath)
        if not path:
            sys.exit(1)
    else:
        # Validate local path
        if not os.path.exists(path):
            print(f"ERROR: Path does not exist: {path}")
            sys.exit(1)

    try:
        # Parse based on format
        if iac_format == "terraform":
            result = parse_terraform(path)
        elif iac_format == "cloudformation":
            result = parse_cloudformation(path)
        elif iac_format == "kubernetes":
            result = parse_kubernetes(path)
        elif iac_format == "docker-compose":
            result = parse_docker_compose(path)
        else:
            print(f"ERROR: Unsupported format: {iac_format}")
            print("Supported formats: terraform, cloudformation, kubernetes, docker-compose")
            sys.exit(1)

        # Output JSON result
        print("\n" + "="*60)
        print("PARSE RESULT:")
        print("="*60)
        print(json.dumps(result, indent=2))

        # Check for errors
        if "error" in result:
            sys.exit(1)

    finally:
        # Always clean up temp directory
        if temp_dir:
            cleanup_temp_dir(temp_dir)


if __name__ == "__main__":
    main()
