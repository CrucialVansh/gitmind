import * as vscode from 'vscode';
import { GitMindClient, QueryResult } from './gitmindClient';

export class GitMindSidebarProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'gitmind.sidebarView';
  private _view?: vscode.WebviewView;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _client: GitMindClient
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (data) => {
      switch (data.type) {
        case 'ask': {
          await this.handleAsk(data.value);
          break;
        }
        case 'index': {
          await this.handleIndex();
          break;
        }
      }
    });
  }

  public async askQuery(query: string) {
    if (this._view) {
      this._view.show?.(true);
      this._view.webview.postMessage({ type: 'setQuery', value: query });
      await this.handleAsk(query);
    }
  }

  private async handleAsk(query: string) {
    if (!query || !query.trim()) return;

    this._view?.webview.postMessage({ type: 'loading', value: true });

    try {
      const result: QueryResult = await this._client.ask(query);
      this._view?.webview.postMessage({ type: 'result', value: result });
    } catch (err: any) {
      this._view?.webview.postMessage({
        type: 'error',
        value: err.message || 'Failed to query GitMind',
      });
    } finally {
      this._view?.webview.postMessage({ type: 'loading', value: false });
    }
  }

  private async handleIndex() {
    this._view?.webview.postMessage({ type: 'loading', value: true, message: 'Indexing repository...' });
    try {
      await this._client.index();
      vscode.window.showInformationMessage('GitMind: Repository indexing complete!');
      this._view?.webview.postMessage({ type: 'indexSuccess' });
    } catch (err: any) {
      vscode.window.showErrorMessage(`GitMind Index Error: ${err.message}`);
    } finally {
      this._view?.webview.postMessage({ type: 'loading', value: false });
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitMind</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      background-color: var(--vscode-sideBar-background);
      padding: 12px;
      margin: 0;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    .title {
      font-weight: bold;
      font-size: 1.1em;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .btn-index {
      background-color: transparent;
      color: var(--vscode-textLink-foreground);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 3px;
      padding: 3px 8px;
      cursor: pointer;
      font-size: 0.85em;
    }
    .btn-index:hover {
      background-color: var(--vscode-button-secondaryHoverBackground);
    }
    .input-container {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 16px;
    }
    textarea {
      width: 100%;
      box-sizing: border-box;
      background-color: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      padding: 8px;
      resize: vertical;
      min-height: 60px;
      font-family: inherit;
    }
    textarea:focus {
      outline: 1px solid var(--vscode-focusBorder);
    }
    button.primary {
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 4px;
      padding: 8px 12px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    button.primary:hover {
      background-color: var(--vscode-button-hoverBackground);
    }
    .spinner {
      display: none;
      text-align: center;
      padding: 20px;
      color: var(--vscode-descriptionForeground);
      font-style: italic;
    }
    .result-container {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .badge {
      display: inline-block;
      align-self: flex-start;
      font-size: 0.75em;
      text-transform: uppercase;
      font-weight: bold;
      padding: 2px 6px;
      border-radius: 3px;
      background-color: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
    }
    .answer-card {
      background-color: var(--vscode-editor-background);
      border: 1px solid var(--vscode-widget-border);
      border-radius: 6px;
      padding: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .timeline {
      margin-top: 8px;
      border-top: 1px solid var(--vscode-panel-border);
      padding-top: 8px;
    }
    .timeline-title {
      font-weight: bold;
      font-size: 0.9em;
      margin-bottom: 6px;
      color: var(--vscode-textLink-foreground);
    }
    .timeline-item {
      padding: 6px 0;
      border-left: 2px solid var(--vscode-textLink-activeForeground);
      padding-left: 8px;
      margin-bottom: 6px;
      font-size: 0.9em;
    }
    .timeline-date {
      color: var(--vscode-descriptionForeground);
      font-size: 0.8em;
    }
    .sources {
      font-size: 0.8em;
      color: var(--vscode-descriptionForeground);
      margin-top: 8px;
    }
    .error-card {
      background-color: var(--vscode-inputValidation-errorBackground);
      border: 1px solid var(--vscode-inputValidation-errorBorder);
      padding: 10px;
      border-radius: 4px;
      color: var(--vscode-errorForeground);
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">🧠 GitMind</div>
    <button class="btn-index" id="btnIndex">⚡ Index</button>
  </div>

  <div class="input-container">
    <textarea id="queryInput" placeholder="Why did we switch to gRPC? Where is the retry logic?"></textarea>
    <button class="primary" id="btnAsk">Ask GitMind</button>
  </div>

  <div class="spinner" id="spinner">Searching codebase decisions...</div>
  <div id="errorContainer"></div>
  <div class="result-container" id="resultContainer"></div>

  <script>
    const vscode = acquireVsCodeApi();
    const queryInput = document.getElementById('queryInput');
    const btnAsk = document.getElementById('btnAsk');
    const btnIndex = document.getElementById('btnIndex');
    const spinner = document.getElementById('spinner');
    const resultContainer = document.getElementById('resultContainer');
    const errorContainer = document.getElementById('errorContainer');

    btnAsk.addEventListener('click', () => {
      const q = queryInput.value.trim();
      if (q) {
        vscode.postMessage({ type: 'ask', value: q });
      }
    });

    queryInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        btnAsk.click();
      }
    });

    btnIndex.addEventListener('click', () => {
      vscode.postMessage({ type: 'index' });
    });

    window.addEventListener('message', event => {
      const msg = event.data;
      switch (msg.type) {
        case 'setQuery':
          queryInput.value = msg.value;
          break;
        case 'loading':
          spinner.style.display = msg.value ? 'block' : 'none';
          if (msg.value) {
            errorContainer.innerHTML = '';
            resultContainer.innerHTML = '';
          }
          break;
        case 'error':
          errorContainer.innerHTML = '<div class="error-card">' + msg.value + '</div>';
          break;
        case 'result':
          renderResult(msg.value);
          break;
      }
    });

    function renderResult(res) {
      let html = '';
      if (res.intent) {
        html += '<div class="badge">' + res.intent + '</div>';
      }
      html += '<div class="answer-card">' + escapeHtml(res.answer) + '</div>';

      if (res.decision_arc && res.decision_arc.length > 0) {
        html += '<div class="timeline"><div class="timeline-title">Decision Timeline</div>';
        res.decision_arc.forEach(entry => {
          const d = new Date(entry.date).toLocaleDateString();
          html += '<div class="timeline-item">';
          html += '<div class="timeline-date">' + d + ' · ' + entry.commit_hash.slice(0, 7) + '</div>';
          html += '<div>' + escapeHtml(entry.rationale_summary) + '</div>';
          html += '</div>';
        });
        html += '</div>';
      }

      if ((res.source_commits && res.source_commits.length) || (res.source_sessions && res.source_sessions.length)) {
        html += '<div class="sources">';
        const parts = [];
        if (res.source_commits && res.source_commits.length) {
          parts.push('commits: ' + res.source_commits.map(c => c.slice(0, 7)).join(', '));
        }
        if (res.source_sessions && res.source_sessions.length) {
          parts.push('sessions: ' + res.source_sessions.join(', '));
        }
        html += 'Sources: ' + parts.join(' · ');
        html += '</div>';
      }

      resultContainer.innerHTML = html;
    }

    function escapeHtml(text) {
      if (!text) return '';
      return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  </script>
</body>
</html>`;
  }
}
