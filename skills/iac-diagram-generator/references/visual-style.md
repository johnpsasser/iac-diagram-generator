# Visual Design System

Every diagram MUST follow this standardized visual template for consistency. When
building a Nano Banana Pro prompt, describe these elements in natural language
(full sentences, not keyword lists).

## Canvas & Outer Margins

- "A professional 16:9 landscape architecture diagram"
- "The canvas has a clean white outer margin (at least 60 pixels on all sides) creating breathing room before the page edge"
- "This outer margin ensures no content touches or approaches the canvas boundaries"

## Border Frame (inside the outer margin)

- "A subtle rounded-corner border with a thin dark gray stroke frames all diagram content"
- "Everything — header, zones, connections, legend, and logos — is contained INSIDE this border"
- "An inner padding of 30 pixels separates all content from the border edge"

## Header Section (inside the frame, top 12%)

- "A gradient header bar spans the full width inside the frame, transitioning from deep navy blue (#1a365d) on the left to teal (#0d9488) on the right"
- "The title '[ARCHITECTURE NAME]' appears in large, bold white sans-serif text (like Inter or SF Pro) centered in the header"
- "A subtitle below reads '[Brief Description]' in smaller light gray text"

## Main Canvas (inside the frame, middle 78%)

- "The main area has a very light cool gray background (#f8fafc)"
- "Architectural zones are represented as softly colored rectangular regions with rounded corners and subtle drop shadows"
- "Adequate spacing between zones prevents crowding"

## Footer Section (inside the frame, bottom 10%)

- "A thin footer bar INSIDE the frame contains a compact legend with small icon samples and labels"
- "Cloud provider logo (AWS/Azure/GCP) appears discretely in the bottom-right corner, INSIDE the border frame"
- "The legend and logo have the same inner padding from the border as other content"

# Icon & Visual Style

**Use isometric 3D style (NOT flat official icons):**

- "All resource icons are rendered in a clean isometric 3D style with subtle shadows"
- "Icons have a consistent 30-degree isometric angle and soft gradient fills"
- "Each icon type uses a distinct, harmonious color from a modern tech palette"
- "Icons are crisp, detailed, and visually appealing — like high-end infographic illustrations"

**Color palette for icons:**

- Compute (EC2, Lambda, Containers): Warm orange (#f97316) to coral
- Networking (VPC, Load Balancers, Gateways): Purple (#8b5cf6) to indigo
- Storage (S3, EBS, EFS): Green (#22c55e) to emerald
- Database (RDS, DynamoDB, ElastiCache): Blue (#3b82f6) to sky blue
- Security (IAM, KMS, WAF): Red (#ef4444) to rose
- Analytics (Athena, Glue, Kinesis): Teal (#14b8a6) to cyan

**Zone/layer backgrounds:**

- Public/Internet zone: Very light blue tint (#eff6ff) with dashed blue border
- Private/Application zone: Very light green tint (#f0fdf4) with dashed green border
- Data/Database zone: Very light amber tint (#fffbeb) with dashed amber border
- Security/Governance zone: Very light slate tint (#f1f5f9) with dashed gray border

# Hierarchical Organization

Describe the architecture from outermost to innermost layers:

1. **Cloud Provider / Region Level** — "The diagram shows an AWS architecture in the us-east-1 region"
2. **VPC / Virtual Network Level** — "A VPC labeled 'Production VPC (10.0.0.0/16)' contains all resources" (rectangular containers with dashed borders)
3. **Availability Zone / Subnet Level** — "Inside the VPC, there are three subnets arranged horizontally", e.g. public (10.0.1.0/24), private (10.0.2.0/24), database (10.0.3.0/24)
4. **Resource Level** — describe each resource with its icon type and label, e.g. "An Application Load Balancer icon labeled 'web-alb'", "Three EC2 instance icons labeled 'web-1', 'web-2', 'web-3'"

# Resource Representation

**Compute:** "EC2 instance icons" (orange server icons), "Lambda function icons" (orange lambda symbols), "Container icons for ECS tasks"

**Networking:** "Load balancer icon" (purple distribution icon), "VPC router icon", "Internet gateway icon" (globe icon), "NAT gateway icon"

**Storage:** "S3 bucket icon" (green/orange bucket), "RDS database icon" (blue cylinder), "ElastiCache icon" (orange cache symbol)

**Security:** "Security group represented as a dotted border around resources", "IAM role icon" (orange key/badge), "WAF/firewall icon"

# Connections and Data Flow

**Arrow styles:**

- "All connection arrows are smooth, curved bezier paths (not straight lines) with subtle shadows"
- "Arrow heads are small, elegant triangles"
- "Connection lines have a consistent 3px stroke width"

**Color coding:**

- Internet/External traffic: Bright blue (#3b82f6) solid arrows
- Internal HTTP/REST: Purple (#8b5cf6) solid arrows
- Database connections: Amber (#f59e0b) dashed arrows
- Async/Queue messages: Green (#22c55e) dotted arrows
- Security/Auth flows: Red (#ef4444) solid arrows

**Labels:** "Each arrow has a small pill-shaped label with white background and the protocol/port (e.g., 'HTTPS 443', 'PostgreSQL 5432')", positioned along the arrow path, not overlapping other elements.

**Direction:** "The primary data flow moves left-to-right, with internet entry on the left", "Vertical flows indicate writes going down, reads going up", "Return paths are shown as lighter, thinner arrows parallel to the main flow".

# Labels and Text

- **Always include a title:** "At the very top of the diagram is a prominent title reading '[Architecture Name]'"
- **Always include a subtitle:** "with a subtitle below it stating '[Brief Description]'"
- Enclose all labels in single quotes within the prompt
- Be specific: "The VPC container is labeled 'Production VPC (10.0.0.0/16)'", "The database is labeled 'PostgreSQL RDS (db.t3.medium)'"

# Layout and Composition

- **Orientation:** "Left-to-right flow showing internet traffic entering from the left", "Top-to-bottom hierarchy with VPC at the top"
- **Spacing:** "Resources are evenly spaced with clear separation", "Connection arrows do not overlap", "Labels are positioned next to their resources without overlapping other elements"

# DO / DON'T

**DO:**

- Always use the standardized visual template (16:9 landscape, gradient header, framed border, footer legend)
- Specify isometric 3D icon style — NOT flat official cloud icons
- Use the defined color palette consistently
- Define zones with tinted backgrounds (blue=public, green=private, amber=data)
- Describe curved bezier arrows, not straight lines
- Include pill-shaped labels on arrows with protocol and port
- Start prompts with canvas/frame description before architecture content
- Use narrative descriptions — full sentences describing spatial relationships
- Group resources visually by security boundaries with dotted/dashed borders
- Specify left-to-right data flow as the default orientation
- Include CIDR blocks in zone labels for networks
- End with an aesthetic summary reinforcing "visually stunning, professional" quality

**DON'T:**

- Request "official AWS/Azure/GCP icons" — they produce inconsistent, flat results
- Use white backgrounds — specify "very light cool gray (#f8fafc)" instead
- Forget the header gradient and title placement
- Use straight-line arrows — always specify curved/bezier paths
- Mix icon styles within the same diagram
- Create cluttered diagrams — if >15 resources, split into multiple focused diagrams
- Use generic descriptions like "some servers" — be specific with names and counts
- Omit connection labels — every arrow needs a protocol/port label
- Forget the footer legend, or skip the zone background colors
