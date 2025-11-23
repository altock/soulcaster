import { NextResponse } from 'next/server';
import { ECSClient, RunTaskCommand } from '@aws-sdk/client-ecs';

const ecsClient = new ECSClient({
    region: process.env.AWS_REGION || 'us-east-1',
    credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID || '',
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || '',
    },
});

export async function POST(request: Request) {
    try {
        const { issue_url } = await request.json();

        if (!issue_url) {
            return NextResponse.json(
                { error: 'Missing issue_url' },
                { status: 400 }
            );
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
                        command: [issue_url], // ENTRYPOINT already has 'uv run fix_issue.py'
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
        });
    } catch (error) {
        console.error('Error triggering agent:', error);
        return NextResponse.json(
            { error: 'Internal Server Error', details: error instanceof Error ? error.message : String(error) },
            { status: 500 }
        );
    }
}
