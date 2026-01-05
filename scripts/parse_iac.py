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

# Optional: tfparse for accurate Terraform parsing (requires terraform init)
try:
    from tfparse import load_from_path as tfparse_load
    TFPARSE_AVAILABLE = True
except ImportError:
    TFPARSE_AVAILABLE = False

# Optional: python-hcl2 for HCL2 parsing without terraform init
try:
    import hcl2
    HCL2_AVAILABLE = True
except ImportError:
    HCL2_AVAILABLE = False

# Optional: cfn-lint for accurate CloudFormation parsing
try:
    from cfnlint.decode import cfn_yaml, cfn_json
    from cfnlint.template import Template as CfnTemplate
    CFNLINT_AVAILABLE = True
except ImportError:
    CFNLINT_AVAILABLE = False


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

    Uses a tiered approach:
    1. tfparse (most accurate, requires terraform init)
    2. python-hcl2 (good accuracy, no init required)
    3. regex fallback (basic extraction)
    """
    print(f"Parsing Terraform files in: {path}")

    # Check if .terraform directory exists (needed for tfparse)
    terraform_dir = os.path.join(path, ".terraform") if os.path.isdir(path) else None
    has_terraform_init = terraform_dir and os.path.exists(terraform_dir)

    # Try tfparse first (most accurate)
    if TFPARSE_AVAILABLE and has_terraform_init:
        print("  Using tfparse (terraform init detected)")
        result = parse_terraform_with_tfparse(path)
        if "error" not in result:
            return result
        print(f"  tfparse failed: {result.get('error')}, falling back...")
    elif TFPARSE_AVAILABLE and not has_terraform_init:
        print("  tfparse available but no .terraform/ directory (run 'terraform init' for best results)")

    # Try python-hcl2 next
    if HCL2_AVAILABLE:
        print("  Using python-hcl2")
        result = parse_terraform_with_hcl2(path)
        if "error" not in result:
            return result
        print(f"  hcl2 failed: {result.get('error')}, falling back...")

    # Fall back to regex
    print("  Using regex fallback (basic extraction)")
    return parse_terraform_with_regex(path)


def parse_terraform_with_tfparse(path):
    """
    Parse Terraform using tfparse (Cloud Custodian).
    Provides full expression evaluation and accurate dependency tracking.
    Requires 'terraform init' to have been run.
    """
    try:
        parsed = tfparse_load(path)

        resources = []
        dependencies = {}
        modules = []
        data_sources = []

        # Process each resource type
        for resource_type, resource_instances in parsed.items():
            # Skip non-resource entries
            if resource_type in ('variable', 'output', 'locals', 'terraform', 'provider'):
                continue

            if resource_type == 'module':
                for instance in resource_instances:
                    modules.append({
                        "name": instance.get('__tfmeta', {}).get('label', 'unknown'),
                        "source": instance.get('source', ''),
                    })
                continue

            if resource_type == 'data':
                for instance in resource_instances:
                    meta = instance.get('__tfmeta', {})
                    data_sources.append({
                        "type": meta.get('label', 'unknown'),
                        "name": meta.get('path', 'unknown'),
                    })
                continue

            # Process resources
            for instance in resource_instances:
                meta = instance.get('__tfmeta', {})
                resource_name = meta.get('label', 'unknown')
                full_name = f"{resource_type}.{resource_name}"

                # Extract provider from resource type
                provider = resource_type.split("_")[0] if "_" in resource_type else "unknown"

                resource_data = {
                    "type": resource_type,
                    "name": resource_name,
                    "full_name": full_name,
                    "provider": provider,
                    "attributes": {k: v for k, v in instance.items() if not k.startswith('__')},
                }
                resources.append(resource_data)

                # Extract dependencies from attribute references
                deps = extract_tfparse_dependencies(instance, resource_type)
                if deps:
                    dependencies[full_name] = deps

        return {
            "format": "terraform",
            "parser": "tfparse",
            "resources": resources,
            "modules": modules,
            "data_sources": data_sources,
            "total_resources": len(resources),
            "dependencies": dependencies,
        }

    except Exception as e:
        return {"error": f"tfparse failed: {str(e)}"}


def extract_tfparse_dependencies(resource_attrs, resource_type):
    """
    Extract resource dependencies from tfparse output.
    Looks for references in attribute values.
    """
    dependencies = set()

    def find_references(obj, path=""):
        """Recursively find resource references in attribute values."""
        if isinstance(obj, str):
            # Look for resource references like "aws_subnet.main.id"
            ref_pattern = r'([a-z_]+\.[a-z0-9_-]+)(?:\.[a-z_]+)?'
            for match in re.finditer(ref_pattern, obj):
                ref = match.group(1)
                # Filter out common non-resource patterns
                if not ref.startswith(('var.', 'local.', 'data.', 'module.', 'path.', 'terraform.')):
                    # Validate it looks like a resource reference
                    parts = ref.split('.')
                    if len(parts) == 2 and '_' in parts[0]:
                        dependencies.add(ref)
        elif isinstance(obj, dict):
            for key, value in obj.items():
                if not key.startswith('__'):
                    find_references(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_references(item, f"{path}[{i}]")

    find_references(resource_attrs)
    return list(dependencies)


def parse_terraform_with_hcl2(path):
    """
    Parse Terraform using python-hcl2.
    Good for syntax parsing without terraform init.
    """
    try:
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
        locals_block = {}
        outputs = {}
        all_content = {}

        for tf_file in tf_files:
            print(f"    Reading: {tf_file}")
            try:
                with open(tf_file, 'r') as f:
                    parsed = hcl2.load(f)
                    all_content[tf_file] = parsed

                # Extract resources
                for resource_block in parsed.get('resource', []):
                    for resource_type, instances in resource_block.items():
                        for instance in instances:
                            for resource_name, attrs in instance.items():
                                full_name = f"{resource_type}.{resource_name}"
                                provider = resource_type.split("_")[0] if "_" in resource_type else "unknown"

                                resources.append({
                                    "type": resource_type,
                                    "name": resource_name,
                                    "full_name": full_name,
                                    "provider": provider,
                                    "file": tf_file,
                                    "attributes": attrs,
                                })

                # Extract variables
                for var_block in parsed.get('variable', []):
                    for var_name, var_config in var_block.items():
                        variables[var_name] = {
                            "name": var_name,
                            "file": tf_file,
                            "default": var_config.get('default'),
                            "type": var_config.get('type'),
                            "description": var_config.get('description'),
                        }

                # Extract modules
                for module_block in parsed.get('module', []):
                    for module_name, module_config in module_block.items():
                        modules.append({
                            "name": module_name,
                            "source": module_config.get('source', ''),
                            "file": tf_file,
                        })

                # Extract locals
                for locals_block_item in parsed.get('locals', []):
                    locals_block.update(locals_block_item)

                # Extract outputs
                for output_block in parsed.get('output', []):
                    for output_name, output_config in output_block.items():
                        outputs[output_name] = {
                            "name": output_name,
                            "value": output_config.get('value'),
                            "file": tf_file,
                        }

            except Exception as e:
                print(f"    Warning: Error parsing {tf_file}: {e}")
                continue

        # Extract dependencies from resource attributes
        dependencies = extract_hcl2_dependencies(resources)

        return {
            "format": "terraform",
            "parser": "hcl2",
            "resources": resources,
            "variables": variables,
            "modules": modules,
            "locals": locals_block,
            "outputs": outputs,
            "total_resources": len(resources),
            "dependencies": dependencies,
        }

    except Exception as e:
        return {"error": f"hcl2 parsing failed: {str(e)}"}


def extract_hcl2_dependencies(resources):
    """
    Extract dependencies from HCL2 parsed resources by analyzing attribute references.
    """
    dependencies = {}

    # Build a set of known resource full names
    known_resources = {r["full_name"] for r in resources}

    def find_refs_in_value(value):
        """Find resource references in a value (handles ${} interpolation)."""
        refs = set()

        if isinstance(value, str):
            # Match patterns like: aws_subnet.main.id, ${aws_vpc.main.id}
            patterns = [
                r'\$\{([a-z_]+\.[a-z0-9_-]+)(?:\.[a-z_]+)*\}',  # ${resource.name.attr}
                r'([a-z_]+\.[a-z0-9_-]+)(?:\.[a-z_]+)',  # resource.name.attr
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, value):
                    ref = match.group(1)
                    if ref in known_resources:
                        refs.add(ref)
        elif isinstance(value, dict):
            for v in value.values():
                refs.update(find_refs_in_value(v))
        elif isinstance(value, list):
            for item in value:
                refs.update(find_refs_in_value(item))

        return refs

    for resource in resources:
        full_name = resource["full_name"]
        attrs = resource.get("attributes", {})

        # Find all references in attributes
        refs = find_refs_in_value(attrs)

        # Also check depends_on if present
        depends_on = attrs.get("depends_on", [])
        if isinstance(depends_on, list):
            for dep in depends_on:
                if isinstance(dep, str):
                    # Clean up the reference
                    dep_clean = dep.replace("${", "").replace("}", "").split(".")[0:2]
                    if len(dep_clean) == 2:
                        refs.add(".".join(dep_clean))

        if refs:
            dependencies[full_name] = list(refs)

    return dependencies


def parse_terraform_with_regex(path):
    """
    Parse Terraform using regex (fallback).
    Basic extraction without full HCL understanding.
    """
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
        print(f"    Reading: {tf_file}")
        try:
            with open(tf_file, 'r') as f:
                content = f.read()

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
            print(f"    Warning: Error reading {tf_file}: {e}")
            continue

    return {
        "format": "terraform",
        "parser": "regex",
        "resources": resources,
        "variables": variables,
        "modules": modules,
        "total_resources": len(resources),
        "dependencies": extract_regex_dependencies(resources)
    }


def extract_regex_dependencies(resources):
    """Extract basic dependency information using pattern inference (fallback)."""
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
            if "aws_vpc" in resource_types:
                deps.extend([f"aws_vpc.{name}" for name in resource_types["aws_vpc"]])
            if "aws_subnet" in resource_types:
                deps.extend([f"aws_subnet.{name}" for name in resource_types["aws_subnet"]])
            if "aws_security_group" in resource_types:
                deps.extend([f"aws_security_group.{name}" for name in resource_types["aws_security_group"]])

        elif r_type in ("aws_elb", "aws_lb", "aws_alb"):
            if "aws_subnet" in resource_types:
                deps.extend([f"aws_subnet.{name}" for name in resource_types["aws_subnet"]])
            if "aws_security_group" in resource_types:
                deps.extend([f"aws_security_group.{name}" for name in resource_types["aws_security_group"]])

        elif r_type == "aws_db_instance":
            if "aws_db_subnet_group" in resource_types:
                deps.extend([f"aws_db_subnet_group.{name}" for name in resource_types["aws_db_subnet_group"]])
            if "aws_security_group" in resource_types:
                deps.extend([f"aws_security_group.{name}" for name in resource_types["aws_security_group"]])

        elif r_type == "aws_subnet":
            if "aws_vpc" in resource_types:
                deps.extend([f"aws_vpc.{name}" for name in resource_types["aws_vpc"]])

        elif r_type == "aws_security_group":
            if "aws_vpc" in resource_types:
                deps.extend([f"aws_vpc.{name}" for name in resource_types["aws_vpc"]])

        elif r_type == "aws_lambda_function":
            if "aws_iam_role" in resource_types:
                deps.extend([f"aws_iam_role.{name}" for name in resource_types["aws_iam_role"]])

        if deps:
            dependencies[resource["full_name"]] = deps

    return dependencies


def parse_cloudformation(path):
    """
    Parse CloudFormation template (YAML or JSON).

    Uses a tiered approach:
    1. cfn-lint (most accurate, resolves intrinsic functions)
    2. PyYAML fallback (basic parsing)
    """
    print(f"Parsing CloudFormation template: {path}")

    # Try cfn-lint first (most accurate)
    if CFNLINT_AVAILABLE:
        print("  Using cfn-lint")
        result = parse_cloudformation_with_cfnlint(path)
        if "error" not in result:
            return result
        print(f"  cfn-lint failed: {result.get('error')}, falling back...")

    # Fall back to basic YAML parsing
    print("  Using PyYAML fallback")
    return parse_cloudformation_with_yaml(path)


def parse_cloudformation_with_cfnlint(path):
    """
    Parse CloudFormation using cfn-lint.
    Provides intrinsic function resolution and accurate dependency tracking.
    """
    try:
        # Decode the template using cfn-lint
        if path.endswith('.json'):
            template_data, matches = cfn_json.load(path)
        else:
            template_data, matches = cfn_yaml.load(path)

        if template_data is None:
            return {"error": "Failed to decode template"}

        # Create a cfn-lint Template object for better analysis
        cfn_template = CfnTemplate(path, template_data)

        resources = []
        cfn_resources = template_data.get('Resources', {})
        parameters = template_data.get('Parameters', {})
        outputs = template_data.get('Outputs', {})
        conditions = template_data.get('Conditions', {})

        for logical_id, resource in cfn_resources.items():
            resource_type = resource.get('Type', 'Unknown')
            properties = resource.get('Properties', {})

            # Extract provider and service from type (AWS::EC2::Instance -> AWS, EC2)
            provider_parts = resource_type.split('::')
            provider = provider_parts[0] if len(provider_parts) > 0 else 'Unknown'
            service = provider_parts[1] if len(provider_parts) > 1 else 'Unknown'
            resource_name = provider_parts[2] if len(provider_parts) > 2 else 'Unknown'

            # Get condition if present
            condition = resource.get('Condition')

            resources.append({
                "logical_id": logical_id,
                "type": resource_type,
                "provider": provider,
                "service": service,
                "resource_name": resource_name,
                "properties": properties,
                "condition": condition,
                "depends_on": resource.get('DependsOn', []),
                "metadata": resource.get('Metadata', {}),
            })

        # Extract dependencies using cfn-lint's graph capabilities
        dependencies = extract_cfnlint_dependencies(cfn_resources, parameters)

        return {
            "format": "cloudformation",
            "parser": "cfn-lint",
            "resources": resources,
            "parameters": {k: {
                "type": v.get('Type', 'String'),
                "default": v.get('Default'),
                "description": v.get('Description'),
                "allowed_values": v.get('AllowedValues'),
            } for k, v in parameters.items()},
            "outputs": {k: {
                "value": v.get('Value'),
                "description": v.get('Description'),
                "export": v.get('Export', {}).get('Name'),
            } for k, v in outputs.items()},
            "conditions": list(conditions.keys()),
            "total_resources": len(resources),
            "dependencies": dependencies,
        }

    except Exception as e:
        return {"error": f"cfn-lint parsing failed: {str(e)}"}


def extract_cfnlint_dependencies(resources, parameters):
    """
    Extract dependencies from CloudFormation resources using deep intrinsic function analysis.
    """
    dependencies = {}
    resource_ids = set(resources.keys())
    parameter_ids = set(parameters.keys())

    for logical_id, resource in resources.items():
        deps = set()

        # Explicit dependencies
        depends_on = resource.get('DependsOn', [])
        if isinstance(depends_on, str):
            deps.add(depends_on)
        elif isinstance(depends_on, list):
            deps.update(depends_on)

        # Deep scan for Ref and GetAtt in all properties
        refs = extract_cloudformation_refs_deep(resource, resource_ids, parameter_ids)
        deps.update(refs)

        # Filter to only include resource dependencies (not parameters)
        resource_deps = [d for d in deps if d in resource_ids]

        if resource_deps:
            dependencies[logical_id] = resource_deps

    return dependencies


def extract_cloudformation_refs_deep(obj, resource_ids, parameter_ids, refs=None):
    """
    Recursively extract Ref and GetAtt references from CloudFormation template.
    Handles all intrinsic function formats including short and long forms.
    """
    if refs is None:
        refs = set()

    if isinstance(obj, dict):
        # Handle Ref
        if 'Ref' in obj:
            ref_value = obj['Ref']
            if isinstance(ref_value, str) and ref_value in resource_ids:
                refs.add(ref_value)

        # Handle Fn::GetAtt (long form)
        elif 'Fn::GetAtt' in obj:
            get_att = obj['Fn::GetAtt']
            if isinstance(get_att, list) and len(get_att) > 0:
                if get_att[0] in resource_ids:
                    refs.add(get_att[0])
            elif isinstance(get_att, str):
                # Format: "LogicalId.AttributeName"
                logical_id = get_att.split('.')[0]
                if logical_id in resource_ids:
                    refs.add(logical_id)

        # Handle !GetAtt short form (already parsed as Fn::GetAtt by cfn-lint)

        # Handle Fn::Sub - extract ${Resource} and ${Resource.Attr} references
        elif 'Fn::Sub' in obj:
            sub_value = obj['Fn::Sub']
            if isinstance(sub_value, str):
                # Find ${LogicalId} or ${LogicalId.Attribute} patterns
                import re
                for match in re.finditer(r'\$\{([^}!]+?)(?:\.[^}]+)?\}', sub_value):
                    ref = match.group(1)
                    if ref in resource_ids:
                        refs.add(ref)
            elif isinstance(sub_value, list) and len(sub_value) >= 1:
                # [string, {var: value}] format
                if isinstance(sub_value[0], str):
                    for match in re.finditer(r'\$\{([^}!]+?)(?:\.[^}]+)?\}', sub_value[0]):
                        ref = match.group(1)
                        if ref in resource_ids:
                            refs.add(ref)

        # Handle Fn::If - scan condition branches
        elif 'Fn::If' in obj:
            if_value = obj['Fn::If']
            if isinstance(if_value, list):
                for item in if_value[1:]:  # Skip condition name
                    extract_cloudformation_refs_deep(item, resource_ids, parameter_ids, refs)

        # Handle other Fn:: functions that might contain refs
        else:
            for key, value in obj.items():
                if key.startswith('Fn::'):
                    extract_cloudformation_refs_deep(value, resource_ids, parameter_ids, refs)
                elif not key.startswith('!'):
                    extract_cloudformation_refs_deep(value, resource_ids, parameter_ids, refs)

    elif isinstance(obj, list):
        for item in obj:
            extract_cloudformation_refs_deep(item, resource_ids, parameter_ids, refs)

    return refs


def parse_cloudformation_with_yaml(path):
    """
    Parse CloudFormation using PyYAML (fallback).
    Basic parsing without intrinsic function resolution.
    """
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
        resource_ids = set(cfn_resources.keys())
        parameter_ids = set(parameters.keys()) if parameters else set()

        for logical_id, resource in cfn_resources.items():
            deps = set()

            # Explicit dependencies
            depends_on = resource.get('DependsOn', [])
            if isinstance(depends_on, str):
                deps.add(depends_on)
            elif isinstance(depends_on, list):
                deps.update(depends_on)

            # Implicit dependencies from references
            refs = extract_cloudformation_refs_deep(resource, resource_ids, parameter_ids)
            deps.update(refs)

            if deps:
                dependencies[logical_id] = list(deps)

        return {
            "format": "cloudformation",
            "parser": "yaml",
            "resources": resources,
            "parameters": list(parameters.keys()) if parameters else [],
            "outputs": list(outputs.keys()) if outputs else [],
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
    """
    Parse Kubernetes manifests (YAML) with enhanced relationship detection.

    Identifies four relationship types (inspired by KubeDiagrams):
    - REFERENCE: Direct resource references
    - SELECTOR: Label-based selection (Service -> Pod)
    - OWNER: Ownership hierarchies (Deployment -> ReplicaSet -> Pod)
    - COMMUNICATION: Network policies between pods
    """
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
                    annotations = metadata.get('annotations', {})
                    owner_refs = metadata.get('ownerReferences', [])

                    resource = {
                        "kind": kind,
                        "apiVersion": api_version,
                        "name": name,
                        "namespace": namespace,
                        "labels": labels,
                        "annotations": annotations,
                        "owner_references": owner_refs,
                        "file": yaml_file,
                        "spec": spec,  # Keep full spec for relationship analysis
                    }

                    # Extract kind-specific fields
                    resource.update(extract_kubernetes_kind_fields(kind, spec, metadata))

                    resources.append(resource)

        except Exception as e:
            print(f"  Warning: Error reading {yaml_file}: {e}")
            continue

    # Extract relationships using enhanced detection
    relationships = extract_kubernetes_relationships_enhanced(resources)

    # Group resources by namespace and kind
    by_namespace = {}
    by_kind = {}
    for r in resources:
        ns = r["namespace"]
        kind = r["kind"]
        if ns not in by_namespace:
            by_namespace[ns] = []
        by_namespace[ns].append(f"{kind}/{r['name']}")
        if kind not in by_kind:
            by_kind[kind] = []
        by_kind[kind].append(r["name"])

    return {
        "format": "kubernetes",
        "parser": "enhanced",
        "resources": resources,
        "total_resources": len(resources),
        "namespaces": list(set(r["namespace"] for r in resources)),
        "by_namespace": by_namespace,
        "by_kind": by_kind,
        "relationships": relationships,
        "dependencies": convert_relationships_to_dependencies(relationships),
    }


def extract_kubernetes_kind_fields(kind, spec, metadata):
    """Extract kind-specific fields for Kubernetes resources."""
    fields = {}

    if kind == 'Service':
        fields["selector"] = spec.get('selector', {})
        fields["ports"] = spec.get('ports', [])
        fields["type"] = spec.get('type', 'ClusterIP')
        fields["cluster_ip"] = spec.get('clusterIP')

    elif kind in ('Deployment', 'StatefulSet', 'DaemonSet', 'ReplicaSet'):
        fields["replicas"] = spec.get('replicas', 1)
        fields["selector"] = spec.get('selector', {})
        # Extract pod template labels
        template = spec.get('template', {})
        template_metadata = template.get('metadata', {})
        fields["pod_labels"] = template_metadata.get('labels', {})
        # Extract container info
        pod_spec = template.get('spec', {})
        containers = pod_spec.get('containers', [])
        fields["containers"] = [{
            "name": c.get('name'),
            "image": c.get('image'),
            "ports": c.get('ports', []),
        } for c in containers]
        # Extract volume claims
        fields["volume_claims"] = spec.get('volumeClaimTemplates', [])

    elif kind == 'Ingress':
        fields["rules"] = spec.get('rules', [])
        fields["tls"] = spec.get('tls', [])
        fields["ingress_class"] = spec.get('ingressClassName')

    elif kind == 'ConfigMap':
        fields["data_keys"] = list(metadata.get('data', {}).keys()) if 'data' in metadata else []

    elif kind == 'Secret':
        fields["type"] = metadata.get('type', 'Opaque')
        fields["data_keys"] = list(metadata.get('data', {}).keys()) if 'data' in metadata else []

    elif kind == 'PersistentVolumeClaim':
        fields["storage_class"] = spec.get('storageClassName')
        fields["access_modes"] = spec.get('accessModes', [])
        resources_spec = spec.get('resources', {})
        requests = resources_spec.get('requests', {})
        fields["storage"] = requests.get('storage')

    elif kind == 'PersistentVolume':
        fields["storage_class"] = spec.get('storageClassName')
        fields["capacity"] = spec.get('capacity', {}).get('storage')
        fields["access_modes"] = spec.get('accessModes', [])

    elif kind == 'NetworkPolicy':
        fields["pod_selector"] = spec.get('podSelector', {})
        fields["ingress_rules"] = spec.get('ingress', [])
        fields["egress_rules"] = spec.get('egress', [])
        fields["policy_types"] = spec.get('policyTypes', [])

    elif kind == 'ServiceAccount':
        fields["secrets"] = spec.get('secrets', []) if spec else []

    elif kind == 'Role' or kind == 'ClusterRole':
        fields["rules"] = spec.get('rules', []) if spec else []

    elif kind == 'RoleBinding' or kind == 'ClusterRoleBinding':
        fields["role_ref"] = spec.get('roleRef', {}) if spec else {}
        fields["subjects"] = spec.get('subjects', []) if spec else []

    elif kind == 'Job':
        fields["completions"] = spec.get('completions', 1)
        fields["parallelism"] = spec.get('parallelism', 1)
        template = spec.get('template', {})
        pod_spec = template.get('spec', {})
        containers = pod_spec.get('containers', [])
        fields["containers"] = [{"name": c.get('name'), "image": c.get('image')} for c in containers]

    elif kind == 'CronJob':
        fields["schedule"] = spec.get('schedule')
        job_template = spec.get('jobTemplate', {})
        job_spec = job_template.get('spec', {})
        template = job_spec.get('template', {})
        pod_spec = template.get('spec', {})
        containers = pod_spec.get('containers', [])
        fields["containers"] = [{"name": c.get('name'), "image": c.get('image')} for c in containers]

    return fields


def extract_kubernetes_relationships_enhanced(resources):
    """
    Extract relationships between Kubernetes resources using enhanced detection.

    Relationship types:
    - SELECTOR: Label-based selection (Service -> Pods)
    - OWNER: Ownership hierarchy (Deployment -> ReplicaSet -> Pod)
    - REFERENCE: Direct resource references (Ingress -> Service)
    - COMMUNICATION: Network policies
    - MOUNT: Volume/ConfigMap/Secret mounts
    """
    relationships = []

    # Build indexes for efficient lookup
    by_kind_namespace = {}  # {(kind, namespace): [resources]}
    by_labels = {}  # {namespace: {label_key: {label_value: [resources]}}}

    for resource in resources:
        key = (resource["kind"], resource["namespace"])
        if key not in by_kind_namespace:
            by_kind_namespace[key] = []
        by_kind_namespace[key].append(resource)

        # Index by labels
        ns = resource["namespace"]
        if ns not in by_labels:
            by_labels[ns] = {}
        for label_key, label_value in resource.get("labels", {}).items():
            if label_key not in by_labels[ns]:
                by_labels[ns][label_key] = {}
            if label_value not in by_labels[ns][label_key]:
                by_labels[ns][label_key][label_value] = []
            by_labels[ns][label_key][label_value].append(resource)

    for resource in resources:
        kind = resource["kind"]
        name = resource["name"]
        namespace = resource["namespace"]
        spec = resource.get("spec", {})

        # === SELECTOR relationships ===

        # Service -> Pods (via selector)
        if kind == "Service":
            selector = resource.get("selector", {})
            if selector:
                matching_pods = find_resources_by_selector(
                    selector, namespace, ["Pod", "Deployment", "StatefulSet", "DaemonSet"],
                    by_kind_namespace, resources
                )
                for target in matching_pods:
                    relationships.append({
                        "from": f"Service/{name}",
                        "to": f"{target['kind']}/{target['name']}",
                        "type": "SELECTOR",
                        "namespace": namespace,
                        "selector": selector,
                    })

        # === OWNER relationships ===

        # Deployment/StatefulSet/DaemonSet -> ReplicaSet/Pods (implicit)
        if kind in ("Deployment", "StatefulSet", "DaemonSet"):
            relationships.append({
                "from": f"{kind}/{name}",
                "to": f"Pod/{name}-*",
                "type": "OWNER",
                "namespace": namespace,
                "description": f"{kind} manages Pod replicas",
            })

        # CronJob -> Job
        if kind == "CronJob":
            relationships.append({
                "from": f"CronJob/{name}",
                "to": f"Job/{name}-*",
                "type": "OWNER",
                "namespace": namespace,
            })

        # === REFERENCE relationships ===

        # Ingress -> Service
        if kind == "Ingress":
            rules = resource.get("rules", [])
            for rule in rules:
                host = rule.get("host", "*")
                http = rule.get("http", {})
                for path_config in http.get("paths", []):
                    backend = path_config.get("backend", {})
                    service_name = None
                    service_port = None

                    # Handle different API versions
                    if "serviceName" in backend:  # networking.k8s.io/v1beta1
                        service_name = backend["serviceName"]
                        service_port = backend.get("servicePort")
                    elif "service" in backend:  # networking.k8s.io/v1
                        service_name = backend["service"].get("name")
                        port_info = backend["service"].get("port", {})
                        service_port = port_info.get("number") or port_info.get("name")

                    if service_name:
                        relationships.append({
                            "from": f"Ingress/{name}",
                            "to": f"Service/{service_name}",
                            "type": "REFERENCE",
                            "namespace": namespace,
                            "host": host,
                            "path": path_config.get("path", "/"),
                            "port": service_port,
                        })

        # RoleBinding/ClusterRoleBinding -> Role/ClusterRole
        if kind in ("RoleBinding", "ClusterRoleBinding"):
            role_ref = resource.get("role_ref", {})
            if role_ref:
                role_kind = role_ref.get("kind", "Role")
                role_name = role_ref.get("name")
                if role_name:
                    relationships.append({
                        "from": f"{kind}/{name}",
                        "to": f"{role_kind}/{role_name}",
                        "type": "REFERENCE",
                        "namespace": namespace if kind == "RoleBinding" else "cluster",
                    })

            # Also link to subjects
            subjects = resource.get("subjects", [])
            for subject in subjects:
                subj_kind = subject.get("kind")
                subj_name = subject.get("name")
                subj_ns = subject.get("namespace", namespace)
                if subj_kind and subj_name:
                    relationships.append({
                        "from": f"{kind}/{name}",
                        "to": f"{subj_kind}/{subj_name}",
                        "type": "REFERENCE",
                        "namespace": subj_ns,
                        "description": "grants permissions to",
                    })

        # === MOUNT relationships (ConfigMap, Secret, PVC references) ===

        # Extract volume mounts from workload resources
        if kind in ("Deployment", "StatefulSet", "DaemonSet", "Pod", "Job", "CronJob"):
            template = spec.get("template", spec)  # Pod doesn't have template
            pod_spec = template.get("spec", {})
            volumes = pod_spec.get("volumes", [])

            for volume in volumes:
                vol_name = volume.get("name")

                # ConfigMap volume
                if "configMap" in volume:
                    cm_name = volume["configMap"].get("name")
                    if cm_name:
                        relationships.append({
                            "from": f"{kind}/{name}",
                            "to": f"ConfigMap/{cm_name}",
                            "type": "MOUNT",
                            "namespace": namespace,
                            "volume": vol_name,
                        })

                # Secret volume
                if "secret" in volume:
                    secret_name = volume["secret"].get("secretName")
                    if secret_name:
                        relationships.append({
                            "from": f"{kind}/{name}",
                            "to": f"Secret/{secret_name}",
                            "type": "MOUNT",
                            "namespace": namespace,
                            "volume": vol_name,
                        })

                # PVC volume
                if "persistentVolumeClaim" in volume:
                    pvc_name = volume["persistentVolumeClaim"].get("claimName")
                    if pvc_name:
                        relationships.append({
                            "from": f"{kind}/{name}",
                            "to": f"PersistentVolumeClaim/{pvc_name}",
                            "type": "MOUNT",
                            "namespace": namespace,
                            "volume": vol_name,
                        })

        # === COMMUNICATION relationships (NetworkPolicy) ===

        if kind == "NetworkPolicy":
            pod_selector = resource.get("pod_selector", {})
            ingress_rules = resource.get("ingress_rules", [])
            egress_rules = resource.get("egress_rules", [])

            # NetworkPolicy applies to pods matching selector
            relationships.append({
                "from": f"NetworkPolicy/{name}",
                "to": f"Pods matching {pod_selector}",
                "type": "COMMUNICATION",
                "namespace": namespace,
                "description": "applies network rules to",
            })

            # Ingress rules (who can talk to these pods)
            for rule in ingress_rules:
                from_selectors = rule.get("from", [])
                for from_sel in from_selectors:
                    if "podSelector" in from_sel:
                        relationships.append({
                            "from": f"Pods matching {from_sel['podSelector']}",
                            "to": f"Pods matching {pod_selector}",
                            "type": "COMMUNICATION",
                            "namespace": namespace,
                            "direction": "ingress",
                        })

            # Egress rules (who these pods can talk to)
            for rule in egress_rules:
                to_selectors = rule.get("to", [])
                for to_sel in to_selectors:
                    if "podSelector" in to_sel:
                        relationships.append({
                            "from": f"Pods matching {pod_selector}",
                            "to": f"Pods matching {to_sel['podSelector']}",
                            "type": "COMMUNICATION",
                            "namespace": namespace,
                            "direction": "egress",
                        })

    return relationships


def find_resources_by_selector(selector, namespace, target_kinds, by_kind_namespace, all_resources):
    """Find resources that match a label selector."""
    matching = []

    for target_kind in target_kinds:
        key = (target_kind, namespace)
        candidates = by_kind_namespace.get(key, [])

        for candidate in candidates:
            # Get the labels to match against
            if target_kind in ("Deployment", "StatefulSet", "DaemonSet"):
                # Match against pod template labels
                labels_to_check = candidate.get("pod_labels", {})
            else:
                labels_to_check = candidate.get("labels", {})

            # Check if all selector labels match
            if selector and labels_to_check:
                match = all(
                    labels_to_check.get(k) == v
                    for k, v in selector.items()
                )
                if match:
                    matching.append(candidate)

    return matching


def convert_relationships_to_dependencies(relationships):
    """Convert relationships list to a dependencies dict for diagram generation."""
    dependencies = {}

    for rel in relationships:
        from_resource = rel["from"]
        to_resource = rel["to"]

        if from_resource not in dependencies:
            dependencies[from_resource] = []

        # Only add concrete resource references (not wildcards)
        if "*" not in to_resource and "matching" not in to_resource:
            dependencies[from_resource].append(to_resource)

    return dependencies


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
