# IAM Role Creation Guardrails (AWS account 450410489798)

Read this before creating any **new** IAM role/user in this AWS account — the normal
"auto-create role" flow (console wizards, some SDK defaults) will fail here.

## The issue

This account has an org-level policy (SCP) that denies `iam:CreateRole`, `iam:CreateUser`,
and `iam:Put*PermissionsBoundary` **unless** the role/user being created already has a
permissions boundary attached matching:

```
arn:aws:iam::*:policy/GroupIT_*PermissionBoundary
```

If you try to create a role without that boundary, you'll get an explicit `AccessDenied`,
even if your own user/role otherwise has full IAM permissions.

**Where this bites people:** any AWS Console flow that offers to "create and use a new
service role for you" (e.g. Bedrock AgentCore Evaluations setup, some App Runner/Lambda
console wizards) will silently try to create a role without this boundary — and fail.

## The fix

Always create new roles yourself via CLI (or boto3), explicitly attaching the boundary:

```bash
aws iam create-role \
  --role-name YourNewRoleName \
  --assume-role-policy-document file://trust-policy.json \
  --permissions-boundary arn:aws:iam::450410489798:policy/GroupIT_ProjectPermissionBoundary
```

Then attach whatever permission policies the role actually needs, same as normal.

In a console wizard, look for a "use an existing role" option instead of "create a new
role", and point it at a role you pre-created this way.

## Reference implementation in this repo

[scripts/iam_setup.py](scripts/iam_setup.py)'s `_create_role()` method does exactly this —
every role it creates passes `PermissionsBoundary=self.permission_boundary_arn`. Use it as
a template if you're writing a new script that needs to create a role.

The boundary ARN is also available as `PERMISSION_BOUNDARY` in `.agentcore.env.example`/
`.env.template` (`GroupIT_ProjectPermissionBoundary` — combine with your account ID to get
the full ARN).

## Existing role to copy/reuse instead of creating a new one

`AgentCoreExecutionRole` already has this boundary attached and is used by all deployed
agents in this project. Check it first with:

```bash
aws iam get-role --role-name AgentCoreExecutionRole
aws iam list-attached-role-policies --role-name AgentCoreExecutionRole
aws iam list-role-policies --role-name AgentCoreExecutionRole
```

If it already has the permission you need (e.g. `bedrock:InvokeModel`, access to the
existing DynamoDB tables/Lambdas), you don't need a new role at all — just reuse this one.
Only create a new role if you need permissions this one deliberately doesn't have.

## Quick troubleshooting checklist

If you hit `AccessDenied` while creating a role:
1. Confirm the boundary policy exists: `aws iam get-policy --policy-arn arn:aws:iam::450410489798:policy/GroupIT_ProjectPermissionBoundary`
2. Confirm your `create-role` call includes `--permissions-boundary` with that exact ARN.
3. If using a console wizard, switch it to "use an existing role" and point it at a
   pre-created role instead of letting it auto-create one.
