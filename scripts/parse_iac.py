#!/usr/bin/env python3
"""
IaC Parser
Parses Infrastructure as Code files and extracts resource information.
Supports: Terraform, CloudFormation, Kubernetes, Docker Compose
"""

import os
import sys
import json
import glob as file_glob
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is not installed.")
    print("Please install it with: pip install pyyaml")
    sys.exit(1)


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
        print("\nExamples:")
        print("  python parse_iac.py terraform ./infrastructure")
        print("  python parse_iac.py cloudformation template.yaml")
        print("  python parse_iac.py kubernetes ./k8s")
        print("  python parse_iac.py docker-compose docker-compose.yaml")
        sys.exit(1)

    iac_format = sys.argv[1].lower()
    path = sys.argv[2]

    # Validate path
    if not os.path.exists(path):
        print(f"ERROR: Path does not exist: {path}")
        sys.exit(1)

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


if __name__ == "__main__":
    main()
