/**
 * Tasks API Route - 使用 KnightCoreClient
 * 
 * 与 Gateway 不同，这里直接调用 KnightCore（不是 HTTP API）
 * 但两者最终都通过相同的 KnightCore 管理层！
 */
import { NextRequest, NextResponse } from 'next/server';

// 注意：实际实现需要用 Python 调用
// 这里展示概念性的 TypeScript 接口

interface CreateTaskRequest {
  name: string;
  description: string;
  agent_type?: string;
  work_dir?: string;
}

interface TaskResponse {
  id: string;
  name: string;
  description: string;
  status: string;
  agent_type: string;
  created_at: string;
}

// GET /api/tasks - 列出任务
export async function GET() {
  try {
    // 实际实现：调用 Python KnightCore
    // const client = new KnightCoreClient();
    // const tasks = await client.list_tasks();
    
    // 模拟：转发到 Gateway
    const response = await fetch('http://localhost:8080/api/v1/tasks');
    const result = await response.json();
    
    if (result.success) {
      return NextResponse.json(result.data);
    } else {
      return NextResponse.json({ error: result.error }, { status: 500 });
    }
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch tasks' },
      { status: 500 }
    );
  }
}

// POST /api/tasks - 创建任务
export async function POST(request: NextRequest) {
  try {
    const body: CreateTaskRequest = await request.json();
    
    // 方案 1: 直接调用 KnightCore（需要 Python 桥接）
    // const client = new KnightCoreClient();
    // const task = await client.create_task({
    //   name: body.name,
    //   description: body.description,
    //   agent_type: body.agent_type || 'auto'
    // });
    
    // 方案 2: 转发到 Gateway API（推荐，保持一致性）
    const response = await fetch('http://localhost:8080/api/v1/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: body.name,
        description: body.description,
        agent_type: body.agent_type || 'auto',
        work_dir: body.work_dir || '/tmp'
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      return NextResponse.json(result.data, { status: 201 });
    } else {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to create task' },
      { status: 500 }
    );
  }
}
