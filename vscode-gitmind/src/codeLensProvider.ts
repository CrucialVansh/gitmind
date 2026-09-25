import * as vscode from 'vscode';

export class GitMindCodeLensProvider implements vscode.CodeLensProvider {
  private _onDidChangeCodeLenses: vscode.EventEmitter<void> = new vscode.EventEmitter<void>();
  public readonly onDidChangeCodeLenses: vscode.Event<void> = this._onDidChangeCodeLenses.event;

  public provideCodeLenses(
    document: vscode.TextDocument,
    _token: vscode.CancellationToken
  ): vscode.CodeLens[] | Thenable<vscode.CodeLens[]> {
    const config = vscode.workspace.getConfiguration('gitmind');
    if (!config.get<boolean>('enableCodeLens', true)) {
      return [];
    }

    const codeLenses: vscode.CodeLens[] = [];
    const text = document.getText();
    const lang = document.languageId;

    // Fast regex match for function and class definitions
    const functionRegex = lang === 'python'
      ? /^[ \t]*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(/gm
      : /^[ \t]*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)|^[ \t]*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s+)?\(/gm;

    let match;
    while ((match = functionRegex.exec(text)) !== null) {
      const fnName = match[1] || match[2];
      if (!fnName) continue;

      const position = document.positionAt(match.index);
      const range = new vscode.Range(position, position);

      const codeLens = new vscode.CodeLens(range, {
        title: `🧠 GitMind Rationale: ${fnName}`,
        tooltip: `Query GitMind for decision history regarding ${fnName}`,
        command: 'gitmind.showFunctionRationale',
        arguments: [fnName],
      });

      codeLenses.push(codeLens);
    }

    return codeLenses;
  }
}
