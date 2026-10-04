/* Auto-generated Git DAG Data */
window.GIT_DAG_DATA = {
  "repo": "acme-cloud/unified-api",
  "head_branch": "feature/stripe-v3",
  "head_commit": "c900009000000000000000000000000000000009",
  "master_y": 604.0,
  "generated_at": "2026-09-26T10:36:29.411516",
  "status": {
    "is_dirty": true,
    "dirty_count": 2,
    "changes": [
      "M src/billing/stripe.ts",
      "?? tests/billing_test.ts"
    ]
  },
  "branches": [
    {
      "name": "main",
      "hash": "d000010000000000000000000000000000000010",
      "short_hash": "d000010",
      "is_head": false,
      "is_merged_to_master": true,
      "lane": 0
    },
    {
      "name": "feature/stripe-v3",
      "hash": "c900009000000000000000000000000000000009",
      "short_hash": "c900009",
      "is_head": true,
      "is_merged_to_master": false,
      "lane": 1
    },
    {
      "name": "feature/graphql-gateway",
      "hash": "b800008000000000000000000000000000000008",
      "short_hash": "b800008",
      "is_head": false,
      "is_merged_to_master": false,
      "lane": 2
    },
    {
      "name": "feature/oauth2-providers",
      "hash": "c300003000000000000000000000000000000003",
      "short_hash": "c300003",
      "is_head": false,
      "is_merged_to_master": true,
      "lane": -1
    }
  ],
  "stats": {
    "total_commits": 11,
    "total_branches": 4,
    "total_lanes": 4
  },
  "nodes": [
    {
      "id": "a100001000000000000000000000000000000001",
      "short_id": "a100001",
      "title": "feat: initial architecture with async HTTP router and DI container",
      "author": "Alex Chen",
      "author_full": "Alex Chen <alex.chen@example.com>",
      "date": "2026-09-20T10:00:00",
      "branches": [],
      "tags": [
        "v0.1.0"
      ],
      "is_head": false,
      "is_merge": false,
      "parents": [],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 120,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "b200002000000000000000000000000000000002",
      "short_id": "b200002",
      "title": "feat: JWT session verification & role-based middleware",
      "author": "Alex Chen",
      "author_full": "Alex Chen <alex.chen@example.com>",
      "date": "2026-09-20T16:00:00",
      "branches": [],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "a100001000000000000000000000000000000001"
      ],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 505,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "c300003000000000000000000000000000000003",
      "short_id": "c300003",
      "title": "feat: add Google & GitHub OAuth2 PKCE callback handlers",
      "author": "Sara Jenkins",
      "author_full": "Sara Jenkins <sara.j@example.com>",
      "date": "2026-09-20T22:00:00",
      "branches": [
        "feature/oauth2-providers"
      ],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "b200002000000000000000000000000000000002"
      ],
      "lane": -1,
      "lane_name": "feature/oauth2-providers",
      "lane_color": "#f97316",
      "x": 890,
      "y": 352,
      "width": 300,
      "height": 88,
      "status": "normal",
      "is_wip": false
    },
    {
      "id": "d400004000000000000000000000000000000004",
      "short_id": "d400004",
      "title": "feat: connection pooling with PostgreSQL & Prisma ORM",
      "author": "Alex Chen",
      "author_full": "Alex Chen <alex.chen@example.com>",
      "date": "2026-09-21T04:00:00",
      "branches": [],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "b200002000000000000000000000000000000002"
      ],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 1275,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "e500005000000000000000000000000000000005",
      "short_id": "e500005",
      "title": "Merge pull request #14 from feature/oauth2-providers",
      "author": "Sara Jenkins",
      "author_full": "Sara Jenkins <sara.j@example.com>",
      "date": "2026-09-21T10:00:00",
      "branches": [],
      "tags": [
        "v0.2.0"
      ],
      "is_head": false,
      "is_merge": true,
      "parents": [
        "d400004000000000000000000000000000000004",
        "c300003000000000000000000000000000000003"
      ],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 1660,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "f600006000000000000000000000000000000006",
      "short_id": "f600006",
      "title": "feat: Stripe webhook signature validation and idempotency store",
      "author": "Marcus Brody",
      "author_full": "Marcus Brody <marcus@example.com>",
      "date": "2026-09-21T16:00:00",
      "branches": [
        "feature/stripe-v3"
      ],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "e500005000000000000000000000000000000005"
      ],
      "lane": 1,
      "lane_name": "feature/stripe-v3",
      "lane_color": "#10b981",
      "x": 2045,
      "y": 768,
      "width": 300,
      "height": 88,
      "status": "normal",
      "is_wip": false
    },
    {
      "id": "a700007000000000000000000000000000000007",
      "short_id": "a700007",
      "title": "feat: Redis distributed caching with cluster failover support",
      "author": "Alex Chen",
      "author_full": "Alex Chen <alex.chen@example.com>",
      "date": "2026-09-21T22:00:00",
      "branches": [],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "e500005000000000000000000000000000000005"
      ],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 2430,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "b800008000000000000000000000000000000008",
      "short_id": "b800008",
      "title": "feat: GraphQL federation gateway with Apollo Rover schema compiler",
      "author": "Elena Rostova",
      "author_full": "Elena Rostova <elena@example.com>",
      "date": "2026-09-22T04:00:00",
      "branches": [
        "feature/graphql-gateway"
      ],
      "tags": [],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "a700007000000000000000000000000000000007"
      ],
      "lane": 2,
      "lane_name": "feature/graphql-gateway",
      "lane_color": "#a855f7",
      "x": 2815,
      "y": 976,
      "width": 300,
      "height": 88,
      "status": "normal",
      "is_wip": false
    },
    {
      "id": "c900009000000000000000000000000000000009",
      "short_id": "c900009",
      "title": "feat: subscription billing lifecycle & checkout session creation",
      "author": "Marcus Brody",
      "author_full": "Marcus Brody <marcus@example.com>",
      "date": "2026-09-22T10:00:00",
      "branches": [
        "feature/stripe-v3"
      ],
      "tags": [],
      "is_head": true,
      "is_merge": false,
      "parents": [
        "f600006000000000000000000000000000000006"
      ],
      "lane": 1,
      "lane_name": "feature/stripe-v3",
      "lane_color": "#10b981",
      "x": 3200,
      "y": 768,
      "width": 300,
      "height": 88,
      "status": "branch_tip",
      "is_wip": false
    },
    {
      "id": "d000010000000000000000000000000000000010",
      "short_id": "d000010",
      "title": "feat: OpenTelemetry metrics & distributed W3C trace exporter",
      "author": "Alex Chen",
      "author_full": "Alex Chen <alex.chen@example.com>",
      "date": "2026-09-22T16:00:00",
      "branches": [
        "main"
      ],
      "tags": [
        "v1.0.0"
      ],
      "is_head": false,
      "is_merge": false,
      "parents": [
        "a700007000000000000000000000000000000007"
      ],
      "lane": 0,
      "lane_name": "main",
      "lane_color": "#06b6d4",
      "x": 3585,
      "y": 560,
      "width": 300,
      "height": 88,
      "status": "master",
      "is_wip": false
    },
    {
      "id": "active-wip",
      "short_id": "WIP",
      "title": "WIP: Uncommitted Changes (2 files)",
      "author": "Working Tree",
      "author_full": "Local Working Tree <uncommitted>",
      "date": "2026-09-22T20:00:00",
      "branches": [
        "WIP",
        "feature/stripe-v3"
      ],
      "tags": [],
      "is_head": true,
      "is_wip": true,
      "is_merge": false,
      "parents": [
        "c900009000000000000000000000000000000009"
      ],
      "lane": 1,
      "lane_name": "feature/stripe-v3 (WIP)",
      "lane_color": "#10b981",
      "x": 3585,
      "y": 768,
      "width": 300,
      "height": 88,
      "status": "wip"
    }
  ],
  "edges": [
    {
      "id": "e-a100001-b200002",
      "from": "a100001000000000000000000000000000000001",
      "to": "b200002000000000000000000000000000000002",
      "type": "normal",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN",
      "svg_path": "M 420 604.0 L 505 604.0"
    },
    {
      "id": "e-b200002-c300003",
      "from": "b200002000000000000000000000000000000002",
      "to": "c300003000000000000000000000000000000003",
      "type": "branch_out",
      "is_to_master": false,
      "color": "#f97316",
      "label": "BRANCH: feature/oauth2-providers",
      "svg_path": "M 805 604.0 C 850 604.0, 845 396.0, 890 396.0"
    },
    {
      "id": "e-b200002-d400004",
      "from": "b200002000000000000000000000000000000002",
      "to": "d400004000000000000000000000000000000004",
      "type": "normal",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN",
      "svg_path": "M 805 604.0 L 1275 604.0"
    },
    {
      "id": "e-d400004-e500005",
      "from": "d400004000000000000000000000000000000004",
      "to": "e500005000000000000000000000000000000005",
      "type": "normal",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN",
      "svg_path": "M 1575 604.0 L 1660 604.0"
    },
    {
      "id": "e-c300003-e500005",
      "from": "c300003000000000000000000000000000000003",
      "to": "e500005000000000000000000000000000000005",
      "type": "merge",
      "is_to_master": true,
      "color": "#10b981",
      "label": "MERGE TO MAIN",
      "svg_path": "M 1190 396.0 C 1350 396.0, 1500 604.0, 1660 604.0"
    },
    {
      "id": "e-e500005-f600006",
      "from": "e500005000000000000000000000000000000005",
      "to": "f600006000000000000000000000000000000006",
      "type": "branch_out",
      "is_to_master": false,
      "color": "#10b981",
      "label": "BRANCH: feature/stripe-v3",
      "svg_path": "M 1960 604.0 C 2005 604.0, 2000 812.0, 2045 812.0"
    },
    {
      "id": "e-e500005-a700007",
      "from": "e500005000000000000000000000000000000005",
      "to": "a700007000000000000000000000000000000007",
      "type": "normal",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN",
      "svg_path": "M 1960 604.0 L 2430 604.0"
    },
    {
      "id": "e-a700007-b800008",
      "from": "a700007000000000000000000000000000000007",
      "to": "b800008000000000000000000000000000000008",
      "type": "branch_out",
      "is_to_master": false,
      "color": "#a855f7",
      "label": "BRANCH: feature/graphql-gateway",
      "svg_path": "M 2730 604.0 C 2775 604.0, 2770 1020.0, 2815 1020.0"
    },
    {
      "id": "e-f600006-c900009",
      "from": "f600006000000000000000000000000000000006",
      "to": "c900009000000000000000000000000000000009",
      "type": "normal",
      "is_to_master": false,
      "color": "#10b981",
      "label": "",
      "svg_path": "M 2345 812.0 L 3200 812.0"
    },
    {
      "id": "e-a700007-d000010",
      "from": "a700007000000000000000000000000000000007",
      "to": "d000010000000000000000000000000000000010",
      "type": "normal",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN",
      "svg_path": "M 2730 604.0 L 3585 604.0"
    },
    {
      "id": "trunk-d400004-a700007",
      "from": "d400004000000000000000000000000000000004",
      "to": "a700007000000000000000000000000000000007",
      "type": "master-trunk",
      "is_to_master": true,
      "color": "#06b6d4",
      "label": "MAIN TRUNK",
      "svg_path": "M 1575 604.0 L 2430 604.0"
    },
    {
      "id": "e-active-wip",
      "from": "c900009000000000000000000000000000000009",
      "to": "active-wip",
      "type": "wip",
      "is_to_master": false,
      "color": "#10b981",
      "label": "UNCOMMITTED WORK",
      "svg_path": "M 3500 812.0 L 3585 812.0"
    }
  ],
  "diffs": {
    "a100001000000000000000000000000000000001": {
      "files": [
        {
          "status": "A",
          "path": "src/app.ts"
        },
        {
          "status": "A",
          "path": "package.json"
        }
      ],
      "full_output": "commit a100001\nAuthor: Alex Chen <alex.chen@example.com>\nDate:   2026-09-20T10:00:00\n\n    feat: initial architecture with async HTTP router and DI container\n\ndiff --git a/package.json b/package.json\nnew file mode 100644\n--- /dev/null\n+++ b/package.json\n@@ -0,0 +1,15 @@\n+{\n+  \"name\": \"unified-api\",\n+  \"version\": \"0.1.0\",\n+  \"dependencies\": {\n+    \"fastify\": \"^4.26.0\",\n+    \"zod\": \"^3.22.4\"\n+  }\n+}\ndiff --git a/src/app.ts b/src/app.ts\nnew file mode 100644\n--- /dev/null\n+++ b/src/app.ts\n@@ -0,0 +1,12 @@\n+import Fastify from 'fastify';\n+\n+export const app = Fastify({\n+  logger: true,\n+  trustProxy: true\n+});\n+\n+app.get('/health', async () => {\n+  return { status: 'healthy', uptime: process.uptime() };\n+});"
    },
    "b200002000000000000000000000000000000002": {
      "files": [
        {
          "status": "A",
          "path": "src/auth/jwt.ts"
        },
        {
          "status": "M",
          "path": "src/app.ts"
        }
      ],
      "full_output": "commit b200002\nAuthor: Alex Chen <alex.chen@example.com>\nDate:   2026-09-20T16:00:00\n\n    feat: JWT session verification & role-based middleware\n\ndiff --git a/src/auth/jwt.ts b/src/auth/jwt.ts\nnew file mode 100644\n--- /dev/null\n+++ b/src/auth/jwt.ts\n@@ -0,0 +1,14 @@\n+import jwt from 'jsonwebtoken';\n+\n+export function verifyAuthToken(header: string, secret: string) {\n+  const token = header.replace(/^Bearer\\s+/, '');\n+  return jwt.verify(token, secret);\n+}"
    },
    "c300003000000000000000000000000000000003": {
      "files": [
        {
          "status": "A",
          "path": "src/auth/oauth2.ts"
        }
      ],
      "full_output": "commit c300003\nAuthor: Sara Jenkins <sara.j@example.com>\nDate:   2026-09-20T22:00:00\n\n    feat: add Google & GitHub OAuth2 PKCE callback handlers\n\ndiff --git a/src/auth/oauth2.ts b/src/auth/oauth2.ts\nnew file mode 100644\n--- /dev/null\n+++ b/src/auth/oauth2.ts\n@@ -0,0 +1,12 @@\n+export class OAuth2Client {\n+  async exchangeCode(code: string, verifier: string) {\n+    return fetch('https://oauth2.googleapis.com/token', {\n+      method: 'POST',\n+      body: JSON.stringify({ code, code_verifier: verifier })\n+    });\n+  }\n+}"
    },
    "d400004000000000000000000000000000000004": {
      "files": [
        {
          "status": "A",
          "path": "prisma/schema.prisma"
        }
      ],
      "full_output": "commit d400004\nAuthor: Alex Chen <alex.chen@example.com>\nDate:   2026-09-21T04:00:00\n\n    feat: connection pooling with PostgreSQL & Prisma ORM\n\ndiff --git a/prisma/schema.prisma b/prisma/schema.prisma\nnew file mode 100644\n--- /dev/null\n+++ b/prisma/schema.prisma\n@@ -0,0 +1,9 @@\n+datasource db {\n+  provider = \"postgresql\"\n+  url      = env(\"DATABASE_URL\")\n+}\n+\n+model User {\n+  id        String   @id @default(uuid())\n+  email     String   @unique\n+}"
    },
    "e500005000000000000000000000000000000005": {
      "files": [
        {
          "status": "M",
          "path": "src/app.ts"
        },
        {
          "status": "M",
          "path": "README.md"
        }
      ],
      "full_output": "commit e500005\nAuthor: Sara Jenkins <sara.j@example.com>\nDate:   2026-09-21T10:00:00\n\n    Merge pull request #14 from feature/oauth2-providers\n\n    * Enable social login and PKCE flow"
    },
    "f600006000000000000000000000000000000006": {
      "files": [
        {
          "status": "A",
          "path": "src/billing/stripe.ts"
        }
      ],
      "full_output": "commit f600006\nAuthor: Marcus Brody <marcus@example.com>\nDate:   2026-09-21T16:00:00\n\n    feat: Stripe webhook signature validation and idempotency store\n\ndiff --git a/src/billing/stripe.ts b/src/billing/stripe.ts\nnew file mode 100644\n--- /dev/null\n+++ b/src/billing/stripe.ts\n@@ -0,0 +1,11 @@\n+import Stripe from 'stripe';\n+\n+export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {\n+  apiVersion: '2023-10-16'\n+});\n+\n+export function constructEvent(payload: Buffer, sig: string) {\n+  return stripe.webhooks.constructEvent(payload, sig, process.env.STRIPE_WEBHOOK_SECRET!);\n+}"
    },
    "a700007000000000000000000000000000000007": {
      "files": [
        {
          "status": "A",
          "path": "src/cache/redis.ts"
        }
      ],
      "full_output": "commit a700007\nAuthor: Alex Chen <alex.chen@example.com>\nDate:   2026-09-21T22:00:00\n\n    feat: Redis distributed caching with cluster failover support"
    },
    "b800008000000000000000000000000000000008": {
      "files": [
        {
          "status": "A",
          "path": "src/graphql/schema.graphql"
        }
      ],
      "full_output": "commit b800008\nAuthor: Elena Rostova <elena@example.com>\nDate:   2026-09-22T04:00:00\n\n    feat: GraphQL federation gateway with Apollo Rover schema compiler"
    },
    "c900009000000000000000000000000000000009": {
      "files": [
        {
          "status": "M",
          "path": "src/billing/stripe.ts"
        },
        {
          "status": "A",
          "path": "src/billing/plans.json"
        }
      ],
      "full_output": "commit c900009\nAuthor: Marcus Brody <marcus@example.com>\nDate:   2026-09-22T10:00:00\n\n    feat: subscription billing lifecycle & checkout session creation"
    },
    "d000010000000000000000000000000000000010": {
      "files": [
        {
          "status": "A",
          "path": "src/telemetry/tracer.ts"
        }
      ],
      "full_output": "commit d000010\nAuthor: Alex Chen <alex.chen@example.com>\nDate:   2026-09-22T16:00:00\n\n    feat: OpenTelemetry metrics & distributed W3C trace exporter"
    },
    "active-wip": {
      "files": [
        {
          "status": "M",
          "path": "src/billing/stripe.ts"
        },
        {
          "status": "??",
          "path": "tests/billing_test.ts"
        }
      ],
      "full_output": "diff --git a/src/billing/stripe.ts b/src/billing/stripe.ts\n--- a/src/billing/stripe.ts\n+++ b/src/billing/stripe.ts\n@@ -12,3 +12,7 @@\n+export async function cancelSubscription(id: string) {\n+  return stripe.subscriptions.update(id, { cancel_at_period_end: true });\n+}\n\n=== Untracked New Files ===\n+ tests/billing_test.ts"
    }
  },
  "schema_version": 2,
  "primary_branch": "main"
};
