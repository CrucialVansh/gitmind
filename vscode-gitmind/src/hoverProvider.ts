import * as vscode from 'vscode';
import { GitMindClient } from './gitmindClient';

export class GitMindHoverProvider implements vscode.HoverProvider {
  constructor(private readonly _client: GitMindClient) {}

  public async provideHover(
    document: vscode.TextDocument,
    position: vscode.Position,
    _token: vscode.CancellationToken
  ): Promise<vscode.Hover | null> {
    const config = vscode.workspace.getConfiguration('gitmind');
    if (!config.get<boolean>('enableHover', true)) {
      return null;
    }

    const wordRange = document.getWordRangeAtPosition(position);
    if (!wordRange) return null;

    const word = document.getText(wordRange);
    // Only query for identifier-like words with length >= 4
    if (!word || word.length < 4 || /^\d+$/.test(word)) {
      return null;
    }

    const lineText = document.lineAt(position.line).text;
    const isDefinition = lineText.includes('def ') || lineText.includes('function ') || lineText.includes('class ');
    if (!isDefinition) {
      return null;
    }

    const md = new vscode.MarkdownString();
    md.isTrusted = true;
    md.appendMarkdown(`**🧠 GitMind Decision Memory**\n\n`);
    md.appendMarkdown(`[Ask why ${word} was implemented](command:gitmind.showFunctionRationale?${encodeURIComponent(JSON.stringify([word]))})`);

    return new vscode.Hover(md, wordRange);
  }
}
