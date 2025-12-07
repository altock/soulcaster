import { NextResponse } from 'next/server';
import { ECSClient, RunTaskCommand } from '@aws-sdk/client-ecs';
import { Octokit } from 'octokit';
import { getGitHubToken } from '@/lib/auth';

const ecsClient = new ECSClient({
    region: process.env.AWS_REGION || 'us-east-1',
    credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID || '',
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || '',
    },
});

/**
 * Handles POST requests to trigger the coding agent by verifying or creating a GitHub issue,
 * optionally creating a backend job record, and starting an ECS Fargate task that runs the agent.
 *
 * @param request - Incoming HTTP request with a JSON body. Expected fields (optional): 
 *   `issue_url` (GitHub issue URL to use), `context` or `issue_description` (issue body),
 *   `issue_title`, `repo` (repo name), `owner` (repo owner), `repo_url` (Git URL), and `cluster_id`
 *   (to create a backend tracking job). GitHub authentication (via getGitHubToken) is required
 *   to verify or create issues.
 * @returns A JSON HTTP response. On success, returns an object with `success: true`, `message`,
 *   `taskArn`, and the resolved `issue_url`. On failure, returns an error object with `error`
 *   and `details` and an appropriate HTTP status code.
 */
export async function POST(request: Request) {
    try {
        const body = await request.json();
        const githubToken = await getGitHubToken();

        console.log('Trigger Agent Request:', {
            hasGithubToken: !!githubToken,
            bodyKeys: Object.keys(body)
        });
        let { issue_url } = body;
        const { context, issue_title, issue_description, repo: paramRepo, owner: paramOwner, repo_url } = body;
        const issueBody = issue_description || context;

        // Verify issue_url if provided
        if (issue_url && githubToken) {
            try {
                // Parse URL: https://github.com/owner/repo/issues/123
                const match = issue_url.match(/github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/);
                if (match) {
                    const [_, owner, repo, issue_number] = match;
                    const octokit = new Octokit({ auth: githubToken });
                    await octokit.rest.issues.get({
                        owner,
                        repo,
                        issue_number: parseInt(issue_number),
                    });
                    // If successful, issue exists
                } else {
                    console.warn('Invalid GitHub issue URL format:', issue_url);
                    // We allow it to proceed if it doesn't match regex (might be different format?),
                    // but usually we should probably fail. The user asked to "check if that issue exists".
                    // Let's enforce the check if it looks like a GitHub URL.
                    return NextResponse.json(
                        { error: 'Invalid GitHub issue URL format' },
                        { status: 400 }
                    );
                }
            } catch (error) {
                console.error('Failed to verify issue:', error);
                return NextResponse.json(
                    { error: 'Issue not found or inaccessible', details: String(error) },
                    { status: 404 }
                );
            }
        }

        // If no issue_url provided, try to create one from context
        if (!issue_url) {
            if (issueBody && githubToken) {
                try {
                    const octokit = new Octokit({ auth: githubToken });
                    let owner = paramOwner || process.env.GITHUB_OWNER;
                    let repo = paramRepo || process.env.GITHUB_REPO;

                    // If repo_url is provided, try to extract owner/repo from it
                    if (repo_url) {
                        const match = repo_url.match(/github\.com\/([^/]+)\/([^/]+)/);
                        if (match) {
                            owner = match[1];
                            repo = match[2].replace('.git', ''); // Handle .git extension if present
                        }
                    }

                    if (!owner || !repo) {
                        console.error('Missing owner/repo details');
                        return NextResponse.json(
                            { error: 'Missing GitHub repo details. Provide repo/owner params or configure env vars.' },
                            { status: 400 }
                        );
                    }

                    // Create a new issue
                    const title = issue_title || `Automated Fix Request: ${new Date().toISOString()}`;
                    const newIssue = await octokit.rest.issues.create({
                        owner,
                        repo,
                        title: title.substring(0, 256), // GitHub title limit
                        body: issueBody || `Fix requested for cluster at ${new Date().toISOString()}`,
                    });

                    issue_url = newIssue.data.html_url;
                    console.log(`Created new GitHub issue: ${issue_url}`);
                } catch (ghError) {
                    console.error('Failed to create GitHub issue:', ghError);
                    return NextResponse.json(
                        { error: 'Failed to create GitHub issue', details: String(ghError) },
                        { status: 500 }
                    );
                }
            } else {
                return NextResponse.json(
                    {
                        error: 'Configuration Error',
                        details: 'Missing issue_url. To create an issue automatically, provide issue_description (or context) plus repo_url/owner+repo and ensure you are authenticated with GitHub.'
                    },
                    { status: 400 }
                );
            }
        }

        if (!issue_url) {
            return NextResponse.json(
                { error: 'Failed to resolve issue_url' },
                { status: 400 }
            );
        }

        // Create a job record in backend
        let jobId = null;
        const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
        // We assume cluster ID might be passed in body, or we might need to infer it?
        // The current trigger-agent API doesn't strictly require cluster_id, but start_fix passes it.
        // Let's check if we can get cluster_id from body or context.
        // Actually start_fix endpoint calls this.
        // We should probably accept cluster_id in the body of this endpoint.

        const { cluster_id } = body;
        if (cluster_id) {
            try {
                const jobRes = await fetch(`${BACKEND_URL}/jobs`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cluster_id }),
                });
                if (jobRes.ok) {
                    const jobData = await jobRes.json();
                    jobId = jobData.job_id;
                    console.log(`Created tracking job: ${jobId}`);
                } else {
                    console.error('Failed to create tracking job:', await jobRes.text());
                }
            } catch (e) {
                console.error('Error creating tracking job:', e);
            }
        }

        const envOverrides = [
            { name: "BACKEND_URL", value: BACKEND_URL },
        ];
        if (jobId) {
            envOverrides.push({ name: "JOB_ID", value: jobId });
        }

        // Pass the user's session token to the agent
        if (githubToken) {
            envOverrides.push({ name: "GH_TOKEN", value: githubToken });
        }

        const command = new RunTaskCommand({
            cluster: process.env.ECS_CLUSTER_NAME,
            taskDefinition: process.env.ECS_TASK_DEFINITION,
            launchType: 'FARGATE',
            networkConfiguration: {
                awsvpcConfiguration: {
                    subnets: process.env.ECS_SUBNET_IDS?.split(',') || [],
                    securityGroups: process.env.ECS_SECURITY_GROUP_IDS?.split(',') || [],
                    assignPublicIp: 'ENABLED',
                },
            },
            overrides: {
                containerOverrides: [
                    {
                        name: 'coding-agent',
                        command: jobId ? [issue_url, '--job-id', jobId] : [issue_url],
                        environment: envOverrides,
                    },
                ],
            },
        });

        const response = await ecsClient.send(command);

        if (response.failures && response.failures.length > 0) {
            console.error('Fargate task failures:', response.failures);
            return NextResponse.json(
                { error: 'Failed to start task', details: response.failures },
                { status: 500 }
            );
        }

        const taskArn = response.tasks?.[0]?.taskArn;
        console.log(`Started Fargate task: ${taskArn}`);

        return NextResponse.json({
            success: true,
            message: 'Agent triggered successfully',
            taskArn: taskArn,
            issue_url: issue_url // Return the used (or created) issue URL
        });
    } catch (error) {
        console.error('Error triggering agent:', error);
        return NextResponse.json(
            { error: 'Internal Server Error', details: error instanceof Error ? error.message : String(error) },
            { status: 500 }
        );
    }
}