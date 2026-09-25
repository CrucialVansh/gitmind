import * as vscode from 'vscode';
import { GitMindClient } from './gitmindClient';
import { GitMindSidebarProvider } from './sidebarProvider';
import { GitMindCodeLensProvider } from './codeLensProvider';
import { GitMindHoverProvider } from './hoverProvider';

export function activate(context: vscode.ExtensionContext) {
  const client = new GitMindClient();
  const sidebarProvider = new GitMindSidebarProvider(context.extensionUri, client);

  // Register Webview View
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      GitMindSidebarProvider.viewType,
      sidebarProvider
    )
  );

  // Register Commands
  context.subscriptions.push(
    vscode.commands.registerCommand('gitmind.ask', async () => {
      const query = await vscode.window.showInputBox({
        prompt: 'Ask GitMind about a decision in your codebase',
        placeHolder: 'e.g. why does fetchUserWithRetry only retry on 503?',
      });
      if (query) {
        await sidebarProvider.askQuery(query);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('gitmind.index', async () => {
      vscode.window.showInformationMessage('GitMind: Indexing repository in background...');
      try {
        await client.index();
        vscode.window.showInformationMessage('GitMind: Repository indexing complete!');
      } catch (err: any) {
        vscode.window.showErrorMessage(`GitMind Index Error: ${err.message}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('gitmind.showFunctionRationale', async (functionName?: string) => {
      let fn = functionName;
      if (!fn) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          const selection = editor.selection;
          fn = editor.document.getText(selection).trim();
        }
      }
      if (fn) {
        const query = `why was ${fn} implemented and changed?`;
        await sidebarProvider.askQuery(query);
      }
    })
  );

  // Register CodeLens Provider for Python and JS/TS
  const supportedLanguages = ['python', 'typescript', 'javascript', 'typescriptreact', 'javascriptreact'];
  const codeLensProvider = new GitMindCodeLensProvider();
  for (const lang of supportedLanguages) {
    context.subscriptions.push(
      vscode.languages.registerCodeLensProvider({ language: lang }, codeLensProvider)
    );
  }

  // Register Hover Provider
  const hoverProvider = new GitMindHoverProvider(client);
  for (const lang of supportedLanguages) {
    context.subscriptions.push(
      vscode.languages.registerHoverProvider({ language: lang }, hoverProvider)
    );
  }
}

export function deactivate() {}
