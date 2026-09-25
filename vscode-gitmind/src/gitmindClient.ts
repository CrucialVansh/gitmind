import * as vscode from 'vscode';
import { execFile, spawn } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

export interface DecisionArcEntry {
  date: string;
  commit_hash: string;
  rationale_summary: string;
  source_chunk_id: string;
}

export interface QueryResult {
  query: string;
  intent: 'structural' | 'rationale' | 'episode';
  answer: string;
  decision_arc: DecisionArcEntry[];
  source_commits: string[];
  source_sessions: string[];
  token_count: number;
}

export class GitMindClient {
  private getExecutablePath(): string {
    const config = vscode.workspace.getConfiguration('gitmind');
    return config.get<string>('executablePath') || 'gitmind';
  }

  private getWorkspaceFolder(): string {
    const folders = vscode.workspace.workspaceFolders;
    if (folders && folders.length > 0) {
      return folders[0].uri.fsPath;
    }
    return process.cwd();
  }

  /**
   * Ask GitMind a question and parse the JSON output.
   */
  public async ask(query: string): Promise<QueryResult> {
    const exe = this.getExecutablePath();
    const repo = this.getWorkspaceFolder();

    try {
      const { stdout } = await execFileAsync(
        exe,
        ['ask', query, '--repo', repo, '--json'],
        { cwd: repo, maxBuffer: 10 * 1024 * 1024 }
      );
      return JSON.parse(stdout) as QueryResult;
    } catch (err: any) {
      // If gitmind is in a virtualenv or custom path, try python -m gitmind.cli
      try {
        const { stdout } = await execFileAsync(
          'python3',
          ['-m', 'gitmind.cli', 'ask', query, '--repo', repo, '--json'],
          { cwd: repo, maxBuffer: 10 * 1024 * 1024 }
        );
        return JSON.parse(stdout) as QueryResult;
      } catch (innerErr: any) {
        throw new Error(`GitMind failed: ${err.message || err}`);
      }
    }
  }

  /**
   * Run gitmind index in a terminal or child process.
   */
  public async index(rebuild = false): Promise<string> {
    const exe = this.getExecutablePath();
    const repo = this.getWorkspaceFolder();
    const args = ['index', repo];
    if (rebuild) {
      args.push('--rebuild');
    }

    try {
      const { stdout } = await execFileAsync(exe, args, { cwd: repo });
      return stdout;
    } catch (err: any) {
      const { stdout } = await execFileAsync('python3', ['-m', 'gitmind.cli', ...args], { cwd: repo });
      return stdout;
    }
  }
}
