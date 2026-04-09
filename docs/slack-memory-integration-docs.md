# **Claude Agent SDKとDockerを活用したマルチユーザー対応Slackパーソナルエージェントの実装と記憶管理アーキテクチャ**

## **序論とエンタープライズAIエージェントの基本要件**

現代のエンタープライズ環境において、単一のステートレスな対話型AIから、自律的かつ継続的にタスクを実行するステートフルなAIエージェントへの移行が急速に進んでいる。企業内のコミュニケーションのハブであるSlack上で、複数人が同時にアクセスでき、かつ過去の文脈を正確に維持しながら作業を行う「デジタルな同僚」に対する需要はかつてないほど高まっている。この要件を満たすためには、単なるチャットボットの開発を超えた、堅牢なシステムアーキテクチャの構築が不可欠となる。

本分析では、Claude Agent SDKをコアエンジンとして採用し、Dockerコンテナ上で動作するマルチユーザー対応のSlackパーソナルエージェントを構築するための最適なアーキテクチャ設計とベストプラクティスを詳解する。特に、スレッド単位の短期記憶と会社全体の長期的な記憶（ナレッジベース）の構築・管理手法に焦点を当てる。また、開発コミュニティで注目を集めているOpenAgents Workspaceのようなオープンソースソフトウェア（OSS）ツールを連携させることで、目標とするSlack連携や記憶管理が達成可能かどうかについても包括的な調査と評価を行う。

エージェントが自律性を持つということは、プロンプトの入力に対してテキストを返すだけでなく、ファイルシステムを操作し、APIを呼び出し、シェル環境でコードを実行する権限を持つことを意味する。Claude Agent SDKは、従来のステートレスなLLM APIとは異なり、永続的なシェル環境でのコマンド実行、ファイル操作、および過去のインタラクションのコンテキストを保持したツール実行を管理する長期間稼働（Long-Running）プロセスとして機能するよう設計されている1。このような高度な機能を提供するSDKをエンタープライズのマルチユーザー環境で安全に展開するためには、分離された保護実行環境、非同期通信によるセキュアなインターフェース、そしてコンテキストウィンドウの限界を克服する高度なハイブリッド記憶管理システムという、複数の技術的柱を統合する必要がある。

## **Claude Agent SDKおよびDockerを用いた基盤アーキテクチャ設計**

エンタープライズレベルのAIエージェントを構築する際、最も重要となるのは、エージェントの「頭脳」となるLLMと、「手足」となる実行環境をどのように統合し、かつ安全に分離するかというアーキテクチャの基本設計である。このセクションでは、Claude Agent SDKの特性と、Dockerによる実行環境のサンドボックス化の手法について詳細に検討する。

### **Claude Agent SDKとClaude Codeの機能的差異と選択基準**

開発者がAnthropicの技術スタックを利用してエージェントを構築する場合、Claude Code（CLIツール）とClaude Agent SDKのいずれかを選択、あるいは組み合わせて使用することになる。これら二つの技術は密接に関連しているが、アーキテクチャ上の役割は大きく異なる。Claude Codeは、開発者のローカルターミナル内で動作し、ファイルシステムの読み書きやコマンドの実行を行う強力なアシスタントであるが、基本的にはCLIアプリケーションとしてパッケージ化されているため、Slackのバックエンドとして直接稼働させるには一定のラッパー処理が必要となる2。一方、Claude Agent SDKは、Claude Codeを駆動する基盤技術そのものをPythonやTypeScriptのコンポーザブルなライブラリとして提供するものである3。

Slack経由で複数のユーザーが同時にアクセスし、複雑な状態管理や外部データベース（記憶層）との連携を必要とするシステムにおいては、Claude Agent SDKの採用が強く推奨される。SDKを利用することで、開発者はモデルパラメータ、キャッシュ機構、プロンプトの構造、ツール実行のロジック、そして何よりもセッションのライフサイクルをプログラムから完全に制御することが可能となるからである3。エージェントが「いつ記憶を検索し、いつ外部APIを叩くか」といった高度なオーケストレーションは、SDKの低レベルなアクセス権限があって初めて実現可能となる。

### **サンドボックス化とDocker-out-of-Docker (DooD) パターンの実装**

エージェントが自律的にコードを生成し、それをテスト・実行するプロセスにおいて、ホストマシンのセキュリティと整合性を担保することは最優先事項である。Claude Agent SDKは設計上、プロセス分離、リソース制限、ネットワーク制御、およびエフェメラル（一時的）なファイルシステムを提供するサンドボックス化されたコンテナ環境内での実行を前提としている1。

本番環境のデプロイメントパターンとしては、特定のタスクごとにコンテナを立ち上げて破棄する「エフェメラルセッション」と、Slackからの継続的なリクエストを待ち受ける「長期間稼働（Long-Running）セッション」が存在する1。Slackのパーソナルエージェントは常にユーザーからのメンションを待機し、長期間にわたってコンテキストを維持する必要があるため、後者のアプローチが適している。

ローカルや自社インフラ上で安全な実行環境を構築するために、Dockerコンテナ上でClaude Agent SDKを稼働させるアーキテクチャが採用される。この際、エージェント自身がさらに別のコンテナを動的に立ち上げてコードのビルドやテストを行うシナリオ（例えば、エージェントがPythonスクリプトを書き、依存関係を隔離してテストしたい場合）に対応するため、Docker-out-of-Docker（DooD）パターンの実装が極めて有効である4。これは、エージェントが稼働するメインコンテナに対して、ホストマシンの /var/run/docker.sock をボリュームマウントすることで、コンテナ内部からホストのDockerデーモンAPIへのアクセスを許可する手法である4。これにより、エージェントはメインの実行環境を汚染することなく、テスト用の一時的な兄弟コンテナ（Sibling Containers）を生成し、用済みになれば安全に破棄するという高度な自律性を獲得する。

### **Model Context Protocol (MCP) エコシステムによるツール拡張**

Claude Agent SDKのアーキテクチャ上の最大の強みの一つは、Model Context Protocol（MCP）のネイティブサポートである6。従来、AIモデルに外部ツールを接続するためには、APIの仕様に合わせて独自の実装コードを記述する必要があったが、MCPはAIモデルがローカルおよびリモートのリソースとやり取りするための標準化されたプロトコルを提供する4。

Docker環境においては、Docker MCP Toolkitを活用することで、Atlassian（Jira等）、GitHub、Datadog、およびローカルファイルシステムなどの300を超えるコンテナ化されたMCPサーバーを、複雑な依存関係の解決なしにワンクリックでデプロイし、Claude Agent SDKにシームレスに接続することが可能となる2。これにより、Slack上のエージェントに対して「このエラーログを解析し、関連するGitHubのプルリクエストを検索した上で、Jiraにバグチケットを切って」といった、複数のツールを横断する複雑な指示を出すことが可能となる。各MCPサーバーは、エージェントの実行中にサブプロセスとして起動されるか、HTTPやWebSocketを介した独立したサービスとして稼働し、標準化されたJSON形式でエージェントにツールのスキーマと結果を提供する5。

## **Slackインテグレーションとマルチユーザー・セッション管理**

企業における情報のハブであるSlackをエージェントのユーザーインターフェースとして採用することは、人間とAIの協調作業（Agentic Collaboration）を促進する上で極めて自然かつ強力なアプローチである2。Slack上で複数のエンジニアやビジネス担当者が議論している文脈に、エージェントが直接参加し、リアルタイムに過去のインシデント情報を要約したり、バグ調査を行ったりすることで、コンテキストの分断を防ぐことができる。このセクションでは、SlackとDockerコンテナ間のセキュアな通信アーキテクチャと、マルチユーザー環境におけるセッション管理の手法を確立する。

### **Socket Modeアーキテクチャとエンタープライズセキュリティ**

社内ネットワークや閉域網（VPC）内で稼働するDockerコンテナからSlackプラットフォームと通信を行う場合、従来のHTTP Events APIモードではなく、Socket Modeの採用がエンタープライズのベストプラクティスとなる11。

HTTP Events APIを使用する場合、コンテナ側でパブリックなエンドポイントを公開し、SSL証明書を設定した上で、Slackからのインバウンドのリクエストを受け入れるようファイアウォールの設定を変更する必要がある。これは、セキュリティポリシーが厳格な企業においては導入の大きな障壁となる。対照的に、Socket Modeはコンテナ側からSlackのサーバーに対してアウトバウンドのWebSocket接続を確立し、その接続を維持したまま双方向のイベント通信を行うアーキテクチャである12。この方式では、インバウンドのポート開放が一切不要となり、外部からの攻撃ベクトルを大幅に削減できる。

実装手順としては、Slack APIダッシュボードでアプリを作成し、「App-Level Token」（xapp-で始まり、connections:writeスコープを保持）と、「Bot User OAuth Token」（xoxb-で始まる）の2つのトークンを生成する5。これらのトークンをDockerコンテナの環境変数（.env ファイル等）として渡し、SDKを介して初期化処理を行うことで、極めてセキュアなインテグレーションが完了する13。

### **チャンネルとスレッドベースのコンテキストルーティング**

マルチユーザー環境下でのパーソナルエージェントの運用において、最も複雑な課題となるのがコンテキストのルーティングである。複数のユーザーが別々のチャンネルやダイレクトメッセージで同時にエージェントに指示を出した場合、エージェントは自分が今どのプロジェクトの、どの文脈について作業しているのかを正確に識別しなければならない。

この課題を解決するためには、Slackのチャンネルと、コンテナ内の特定のプロジェクトディレクトリや作業スコープを動的にマッピングする設計が必要となる。例えば、projects.json のような設定ファイルを用意し、{"\#frontend-v2": "/app/projects/frontend", "\#backend-api": "/app/projects/backend"} のように定義するアプローチが存在する14。エージェントはSlackからイベントを受信した際、メッセージのメタデータに含まれるチャンネルIDを読み取り、対応するディレクトリに作業コンテキストを切り替える。これにより、特定のチャンネルに紐づくコードベースや CLAUDE.md などのローカル設定ファイルが自動的に適用されるため、ユーザーはいちいち前提条件を説明する手間を省くことができる14。

さらに、会話の単位としてはSlackのスレッド機能を活用する。Slackから送信される assistant\_thread\_started イベントやスレッドID（ts または thread\_ts）を捕捉し、これをClaude Agent SDK内部のコンテキストマネージャーのセッションIDとしてバインドする15。ユーザーが同一スレッド内で返信を続ける限り、エージェントはそのスレッド固有の履歴と作業状態を維持したまま対話を継続できる。

### **アクセス制御と権限昇格の管理**

自律的なエージェントに対して、どこまでの操作権限を与えるかは、システム設計における重大な決定事項である。Claude Agent SDKには権限モードの設定が存在し、permission\_mode="bypassPermissions" を指定することで、エージェントはツール実行のたびにユーザーの許可を求めることなく、完全に自律的に連続した操作を行うことが可能になる6。

しかしながら、エンタープライズのマルチユーザー環境において、すべての操作を無条件で許可することはセキュリティ上許容されない。ここで採用すべきベストプラクティスは、Human-in-the-loop（人間の介入）を前提とした非同期承認フローの構築である。エージェントが情報の検索やコードの分析といった読み取り専用（Read-only）の操作を行う場合は自動実行を許可するが、本番環境のデータベースの変更、ファイルの削除、プルリクエストの作成など、破壊的または影響の大きい操作（Write/Execute）を実行しようとした瞬間にプロセスを一時停止するよう設計する。一時停止したエージェントはSlackスレッド上にボタンを含むインタラクティブなメッセージを投稿し、人間が「承認」または「拒否」を選択するまで待機する17。このプロセスにより、操作のスピードと組織のセキュリティ要件を高いレベルで両立させることができる。

## **スレッド単位の短期記憶（Working/Session Memory）の構築**

Slackインテグレーションが整った後、次に解決すべき中核的な課題は「記憶の管理」である。AIエージェントにおける記憶とは、単なるチャット履歴の保存ではなく、認知アーキテクチャの設計そのものである。LLMにすべての会話履歴とプロジェクトファイルをプロンプトとして毎ターン渡し続ける「コンテキストの詰め込み（Context Stuffing）」アプローチは、APIコストの急増、応答速度（レイテンシ）の悪化を引き起こすだけでなく、本当に重要な情報が長文の中に埋もれて無視される「Lost in the middle」現象を誘発する18。したがって、目的に応じた複数の記憶層を設計することが不可欠である。

本セクションでは、現在進行中のタスクを首尾一貫して遂行するための「短期記憶（Working Memory および Session Memory）」の構築手法について詳述する。これは、人間が会話中に一時的に情報を保持するワーキングメモリや、特定の作業セッション中の短期的な文脈に相当する20。

### **コンテキストウィンドウの限界と状態追跡の基本**

短期記憶の管理において最初に意識すべきは、モデルが処理できるコンテキストウィンドウ（トークン数の上限）の制約である。Claude 4.6などの最新モデルは高度なコンテキスト認識（Context Awareness）機能を備えており、エージェント自身が自分の「トークン予算」の残量を動的に把握することが可能である21。

システムプロンプトの設計において、この特性を最大限に引き出すためのベストプラクティスが存在する。エージェントに対して、「トークン予算の限界が近づいたからといって、タスクを早期に放棄したり中途半端な状態で終了してはならない。コンテキストウィンドウが自動的にリフレッシュ（圧縮）される前に、自身の現在の進行状況、得られた洞察、および次に行うべきステップを必ず記憶に保存すること」という明示的な指示（インセンティブの付与）を記述する21。この指示により、エージェントは単なる応答システムから、自身の状態を監視し続ける状態機械（State Machine）へと進化する。

### **CLAUDE.mdとローカルファイルシステムを用いた状態の永続化**

コンテキストウィンドウがリフレッシュされた際、エージェントがスムーズに作業を再開できるよう、短期記憶をローカルファイルシステム上に物理的なファイルとして書き出す手法が、実践的なベストプラクティスとして確立されている。

1. **CLAUDE.mdの活用**: プロジェクトのルートディレクトリに配置する CLAUDE.md ファイルは、エージェントにプロジェクト特有の規約、ビルドコマンド、テスト手法を伝えるための極めて重要なコンポーネントである。プロンプトエンジニアリングの観点から、このファイルにはエージェントが推測できるような標準的な言語仕様を含めるのではなく、チーム固有の命名規則、避けるべきアンチパターン、インフラ環境の特殊な設定など、高シグナルな情報を記載すべきである22。このファイルはセッションが開始されるたびに読み込まれ、エージェントの基本的な振る舞いを定義する。  
2. **ワークログベースの状態追跡**: 長期間にわたる複雑なコーディングやデバッグタスクにおいて、エージェントに自らの足跡を記録させる。具体的には、タスクの各フェーズにおいて、references.md（参照したファイルや外部ドキュメントのリスト）、findings.md（バグの原因やアーキテクチャ上の発見事項）、および decisions.md（なぜ特定のアプローチを採用または破棄したかの決定理由）という3つのファイルを生成し、更新させ続ける18。この「追跡可能な証拠チェーン（Traceable Evidence Chain）」を形成することで、エージェントは「なぜこのコードがこのようになっているか」という背景をファイルから即座に引き出すことができ、自身の限られたコンテキストウィンドウを他の高度な推論タスクに解放することが可能となる18。  
3. **テストを記憶として扱う**: さらに高度な手法として、テストコードそのものをエージェントの長期的かつ不変の記憶として機能させるアプローチがある。新しい機能の実装やバグ修正に着手する際、最初のコンテキストウィンドウ内でエージェントに網羅的なテストスクリプトを記述させる。そしてシステムプロンプトで「テストを削除したり、都合よく書き換えたりすることは絶対に容認されない」と厳格に指示する。コンテキストがリフレッシュされた後、エージェントは自身の状態を見失うかもしれないが、このテストスクリプトを再実行し、出力されるエラーログを解析することで、自分がどこまで作業を進め、次に何を修正すべきかをファイルシステムの状態から即座に「再発見」することができる21。

### **思考プロセス（Extended Thinking）と記憶の結合**

短期記憶を効果的に運用するためには、情報の保存だけでなく、情報の「検索と適用」のプロセスを高度化する必要がある。Claude 4.6などのモデルで利用可能な「Extended Thinking（拡張された思考）」機能を有効にすることで、エージェントは最終的なテキスト出力を生成する前に、非表示または要約された \<thinking\> ブロック内でステップバイステップの推論を行う21。

この思考プロセスにおいて、エージェントが外部ツールを呼び出す順序や、どの記憶を参照すべきかを推論する「インターリーブ思考（Interleaved Thinking）」が発動する。例えば、エージェントは「ユーザーが特定の認証ミドルウェアのバグについて言及している。記憶ツールを使って昨日の類似バグの対応履歴を検索すべきだが、その前にローカルの auth.py を読み込んで現在の実装状況を確認しよう」といった計画を内部で立案し、ツールを順次実行する21。この推論プロセスにより、盲目的に全てのファイルを検索してコンテキストを溢れさせるような非効率な挙動が抑止され、記憶の精度とレイテンシのバランスが最適化される。

## **会社全体の長期的なメモリ（Organizational Memory）の構築・管理**

短期記憶が個別のタスクやスレッドを完了させるために機能するのに対し、長期記憶（Long-term Memory / Organizational Memory）は、タスクをまたいで永続的に保持されるべき知識の集合体である。ユーザーの個人的な嗜好、企業全体のシステムアーキテクチャ図、過去数年分の障害対応ログなどがこれに該当する20。エージェントがセッションを開始するたびに、ユーザーが「私たちのプロジェクトはPostgreSQLを使用しています」「テストにはpytestを使用します」といった前提条件を繰り返し入力しなければならない状況は、多大な時間の浪費であり、APIトークンの無駄遣いである23。

この根本的な課題を解決し、エージェントに完全な記憶の連続性を持たせるためには、高度な外部メモリ層の統合が必須となる。本分析では、OSSコミュニティおよびエンタープライズ領域で高い評価を得ている記憶管理フレームワーク「Mem0」を中心に、ベストプラクティスを構築する23。

### **ベクトルデータベースとナレッジグラフによるハイブリッドアプローチ**

従来の記憶システムは、テキストを単純にデータベースに追記していくアプローチや、粗雑な検索・抽出拡張生成（RAG）に依存していた。しかし、これらの手法は人間の記憶の仕組みとは根本的に異なり、不要な情報を大量に拾い上げてしまう精度低下（Precision Failure）を引き起こしやすい19。

優れた記憶アーキテクチャは、人間の記憶と同様に機能すべきである。すなわち、生の会話テキストをそのまま保存するのではなく、インタラクションの中から「重要な事実」を抽出し、トピックごとにクラスタリングし、関連する概念間のつながりを構造化して保存しなければならない19。

Mem0のアーキテクチャは、まさにこのパラダイムを実現している。会話の背後でLLMが重要な事実を自動的に抽出し、Qdrantなどのベクトルデータベースを用いてセマンティック検索（意味論的検索）を可能にする。例えば、ユーザーが過去に「厳格なモードを有効にするのが好きだ」と言及した場合、後日「TypeScriptの好みを教えて」と質問された際に、文脈の意味を理解して適切な記憶をマッチングさせる24。

さらに、Mem0はベクトル検索と「ナレッジグラフ（知識グラフ）」を組み合わせたハイブリッドアプローチを提供する24。Neo4jのようなグラフデータベースを用いて、エンティティ間の関係性（例：「ユーザーA」→「管理している」→「プロジェクトX」→「依存している」→「ライブラリY」）を明示的にマッピングする。LOCOMOベンチマークによる実証研究では、このハイブリッドアプローチを採用したMem0は、すべての会話履歴をコンテキストに含める単純な手法と比較して、精度において約26%の向上を示し、応答のレイテンシを91%低下させ、トークンの消費コストを90%以上削減するという驚異的な成果を上げている23。これは、エージェントが必要な情報のみを正確かつ高速に検索できるようになったことの証明である。

| ベンチマーク指標 | フルコンテキスト（履歴全投入）方式 | Mem0（ハイブリッド記憶アーキテクチャ） | 改善効果 |
| :---- | :---- | :---- | :---- |
| **精度 (Accuracy)** | 基準値 | 基準値 \+ 約26% | 大幅な向上（幻覚・ノイズの減少） |
| **トークン消費量** | 最大（APIコスト高大） | 基準値の10%未満 | **90%以上のコスト削減** |
| **p95 レイテンシ** | 遅延が大きい | 高速な応答 | **91%のレイテンシ低減** |

### **ネームスペース（名前空間）の分離とプライバシー保護**

Slackのようなマルチユーザーが混在するエンタープライズ環境において、最も重大なセキュリティリスクの一つは「記憶の漏洩」と「記憶の汚染」である29。あるエンジニアがエージェントに教えた個人的なAPIキーの扱いや実験的な構成が、他のエンジニアの質問に対する回答に混入してしまえば、システム全体に致命的な脆弱性をもたらす。

この問題に対処するため、記憶システムは厳密なネームスペース（名前空間）による分離を行わなければならない。Mem0では、記憶のスコープを以下の複数の階層に分離して保存することが可能である23。

1. **user\_id レイヤー (Personal Memory)**: 個人に紐づく記憶。個人のコーディングスタイルの好み、特定のユーザーだけが担当するサブシステムの背景知識など。SlackのユーザーIDを user\_id としてMem0に渡すことで、他者がこの領域の記憶にアクセスすることを物理的に遮断する29。  
2. **org\_id レイヤー (Organizational Memory)**: 会社やチーム全体で共有されるべき知識。例えば、全社のコーディング規約、デプロイメントの標準手順、過去のメジャーなシステム障害の解決策（ポストモーテム）など。この領域の記憶は、どのユーザーがエージェントに話しかけても参照可能となる20。  
3. **session\_id / run\_id レイヤー (Session Memory)**: 前述したスレッド固有の短期的な文脈。特定のバグ調査やタスクが完了すれば、自動的にエクスパイア（期限切れ）するか、価値のある情報のみが抽出されて上位レイヤーに昇格する20。

Slack上で複数人が会話するチャンネルにエージェントが参加する場合、エージェントはメッセージの発信者のメタデータを抽出し、その発信者の user\_id に基づいて記憶のスコープを動的に切り替えながら応答を生成するよう実装する必要がある30。これにより、共有のワークスペースにありながら、各ユーザーに対して高度にパーソナライズされ、かつセキュアな体験を提供できる。

### **Claude Agent SDKの記憶ツールとシステムプロンプトの最適化**

Mem0をシステムに統合するための具体的な実装手法として、Mem0は公式にMCPサーバー（mem0-mcp-server）を提供している23。Dockerコンテナ内のClaude Agent SDKにこのMCPサーバーを接続することで、エージェントは add\_memory（記憶の追加）、search\_memories（セマンティック検索）、get\_memories（特定の条件での記憶一覧取得）といった関数をネイティブなツールとして自律的に利用できるようになる23。

しかし、組織の膨大な記憶データに加えて、Jira、GitHub、ローカルファイルなど数百のツールへのアクセス権をエージェントに与える場合、別の問題が発生する。すべてのツール定義とその説明文を初期のシステムプロンプトにロードするだけで、数万トークンを消費してしまうのである。このコンテキストの肥大化を防ぐため、Anthropicが提唱する高度なプロンプトエンジニアリング技術を適用する31。

1. **Tool Search Tool（ツールの動的検索）の導入**: すべてのツール定義を初期ロードするのではなく、頻繁に使用する3〜5個のコアツール（ファイル読み込みや基本的な記憶検索など）のみを常時ロード（defer\_loading: false）しておく。残りの膨大なツール群については、エージェントが「ツールを検索するためのツール」を用いて動的にロードさせる設計とする。システムプロンプトには、「あなたはSlackメッセージング、個人的なファイル管理（個人記憶）、およびJiraやGitHubのような全社的なナレッジベース（組織記憶）ツールにアクセスできます。特定の機能が必要な場合は、まずツール検索を使用してください」というガイドラインを明記する31。これにより、コンテキストウィンドウの最大95%を節約し、推論のためのスペースを確保できる。  
2. **Programmatic Tool Calling (PTC) によるデータ合成**: エージェントが過去のデータベースや長期記憶から大量のログを引き出す際、その生の検索結果がそのままコンテキストウィンドウに流し込まれると、重要な指示が押し出されてしまう。これを回避するため、エージェントにPythonコードを記述させ、サンドボックス環境内で複数のツールを呼び出してデータを集計・処理させた後、最終的な「分析の要約」のみをコンテキストに返却させる手法（PTC）を採用する31。これにより、エージェントは数十万行のログから必要な情報を抽出する際にも、自らのトークンを枯渇させることなく処理を完遂できる。  
3. **\<investigate\_before\_answering\> タグによる幻覚（ハルシネーション）の防止**: エージェントが「過去の記憶」について推測で語ることを防ぐため、システムプロンプトをXMLタグで構造化する。\<investigate\_before\_answering\> というタグを設け、「ユーザーが特定の過去のインシデントやソースコードに言及した場合、推測で答えることは厳重に禁止する。必ず search\_memories ツールまたはファイル読み込みツールを実行して事実を確認してから回答を生成すること」という指示を記述する21。

## **OpenAgents Workspace等OSSツールの検証と連携可能性**

ここまでに確立した、Docker上で稼働するClaude SDKベースのエンジン、Slackインテグレーション、そしてMem0を用いたハイブリッド記憶管理という強力なアーキテクチャを、ゼロから全てスクラッチで開発する必要はない。開発コミュニティにはこれらの概念を実装したOSSツールが多数存在しており、それらを流用・連携させることで開発速度を飛躍的に向上させることができる。

本セクションでは、ユーザーの関心が高い workspace.openagents.org（OpenAgents Workspace）の適合性と、代替となるOSSフレームワーク（Phantom、OpenClaw等）について詳細な比較検証を行う。

### **OpenAgents Workspaceのアーキテクチャと機能評価**

OpenAgents Workspaceは、ターミナルやクラウドの様々な場所に分散している多数のAIエージェント（Claude Code、OpenClaw、Cursorなど）を一つにまとめるための「エージェント版Slack」として設計された永続的なハブである32。

* **共有ワークスペースと永続性**: 各ワークスペースは workspace.openagents.org/abc123 のような永続的なURLを持ち、ユーザーはいつでもこの環境に戻ることができる。  
* **コンテキストの共有とコラボレーション**: このプラットフォームの最大の強みは、複数の異なるエージェントが同じチャネル内で会話のコンテキスト、アップロードされたファイルシステム、そしてライブのブラウザセッションを共有できる点にある32。例えば、スクレイピングを行うエージェントと、そのデータをもとにコードを書くエージェントが、同じ環境内で @メンション を使って互いにタスクを引き継ぐといった高度な協調動作（オーケストレーション）を自然に行うことができる33。

**Slack連携と記憶管理の要件に対する適合性**: ユーザーの目標は「既存の企業のSlackワークスペースから、複数人がパーソナルエージェントにアクセスすること」である。しかし、OpenAgents Workspaceの設計思想は「Slackの代替となる、エージェント専用の新しいUIプラットフォーム」を提供することに主眼が置かれている32。したがって、そのまま導入した場合は、ユーザーは普段のSlackから離れて専用のURLにアクセスしなければならなくなり、本来の目的から逸脱する可能性がある。

ただし、OpenAgentsはイベント駆動型のアーキテクチャを採用しており、拡張層としての「Network SDK」を提供している32。このSDKを利用してカスタムアダプター（ブリッジ）を開発し、企業のSlackのイベントをOpenAgents Workspaceのバックエンドに転送する仕組みを構築すれば、表側は既存のSlack UIを使いながら、裏側でOpenAgentsの強力なマルチエージェントコンテキスト共有やファイル共有機能を活用することは技術的に十分に可能である。記憶管理の面でも、ワークスペース自体が共有ファイルシステムを持つため、前述した CLAUDE.md やワークログファイルを配置する基盤として機能する。

### **Phantom AIエージェントアーキテクチャの比較と応用**

OpenAgents Workspaceが「エージェントの集合場所」であるのに対し、今回の要件（Slack \+ Docker \+ Claude SDK \+ 記憶管理）にピタリと一致する別の強力なOSSソリューションが存在する。それが「Phantom」と呼ばれるAIエージェントプロジェクトである5。

Phantomは、一過性のチャットボットではなく、24時間365日稼働する「永続的なAI同僚」を構築することを目的とした、Claude Agent SDKのラッパーフレームワークである。このアーキテクチャは、本レポートで提唱してきたベストプラクティスを見事に体現している。

* **インフラ基盤**: PhantomはDocker Composeファイル一つで展開され、専用のVMやサーバー上で稼働する。内部で /var/run/docker.sock をマウントするDooDパターンを採用しており、自律的に別のコンテナを立ち上げてコードを実行する能力を持つ5。  
* **ネイティブなSlack連携**: マニフェストファイルを用いたSocket ModeのSlack連携が標準で組み込まれており、環境変数にトークンを設定するだけで即座にSlackボットとして応答を開始する5。  
* **組み込みの記憶層**: 最も注目すべきは、Phantomのコンテナ群の中に、Qdrant（ベクトルデータベース）とOllama（埋め込みモデル）が最初から同梱されている点である5。これにより、セッションをまたいだ永続的なベクトル記憶がデフォルトで機能し、「昨日教えた設定」をエージェントが自律的に記憶して再利用する5。  
* **自己進化能力**: さらに、Phantomはタスク終了後に自身の設定やアーキテクチャを書き換え、別のモデルを使ってその変更を検証するという「自己進化（Self-Evolution）」のメカニズムを備えており、使えば使うほどユーザーの環境に特化して賢くなっていく5。

### **OpenClawおよびLangGraphとのアーキテクチャ比較**

他の有力なOSSツールとの比較も重要である。

* **OpenClaw**: Node.jsベースの自動化フレームワークであり、SlackとのSocket ModeおよびHTTP Events APIの統合において非常に完成度が高い12。しかし、OpenClawのデフォルトの記憶アプローチは「すべての文脈をコンテキストウィンドウに詰め込む」手法に依存しがちであり、APIコストの急増やトークンの無駄遣いが懸念されるという開発者からの指摘が存在する19。  
* **LangGraph**: LangChainエコシステム上に構築された、グラフベースのエージェントオーケストレーションフレームワークである36。LangGraphは、タスクの分岐やエラーハンドリングといったワークフローの制御（ステートの管理）において無類の強さを発揮する37。実際の運用現場においては、「LangGraphとClaude SDKのどちらを使うか」という二者択一ではなく、外枠のオーケストレーション（どのプロセスをいつ実行するか）をLangGraphに任せ、各ノード内での実際の推論とツール実行（コードの生成やサンドボックスの操作）をClaude SDKに委譲するという、ハイブリッドな設計パターンが成功を収めている事例も報告されている38。

| ツール / フレームワーク | アーキテクチャの焦点 | 記憶管理の手法 | Slack連携の容易さ | 本プロジェクトへの適合性 |
| :---- | :---- | :---- | :---- | :---- |
| **OpenAgents Workspace** | マルチエージェントのUIハブと共有ブラウザ | 共有ファイルシステムとコンテキスト | カスタムブリッジ開発が必要 | **中〜高**。複数エージェントを連携させる将来の拡張フェーズで有力。 |
| **Phantom** | Claude SDKの永続化と自己進化 | Qdrant \+ Ollamaによる内蔵ベクトル記憶 | マニフェストとSocket Modeによる即時連携 | **極めて高い**。本プロジェクトの要件を網羅する事実上のブループリント。 |
| **OpenClaw** | Node.jsベースのワークフロー自動化 | 主にコンテキストの詰め込みに依存 | 高度なエンタープライズ設定をサポート | **中**。Claude SDKの深い機能を利用するには追加実装が必要。 |
| **LangGraph** | DAG（有向非巡回グラフ）によるフロー制御 | Checkpoint (短期) と Memory Store (長期) | カスタム実装が必要 | **高**。複雑な社内プロセスの承認フローなどを厳密に制御したい場合に有効。 |

## **システム統合と本番環境へのデプロイメント戦略**

本レポートにおける分析を総括し、ユーザーの要件を満たすための具体的なシステム統合とデプロイメントの戦略を提示する。

最短かつ最も堅牢なアプローチは、**PhantomのOSSアーキテクチャをベース基盤として採用し、そこにMem0の高度なMCP記憶サーバーを統合する構成**である。PhantomはDocker基盤、Claude Agent SDKの長期間稼働プロセス、そしてSlackのSocket Mode連携といった面倒なインフラの配管作業（Plumbing）をすでに解決している5。

この基盤の上に、Phantom内蔵の単純なベクトル記憶を、Mem0のマルチテナント・ナレッジグラフアーキテクチャで置き換えるか、あるいは拡張する。具体的には以下のステップを踏む。

1. **インフラの立ち上げ**: 適切なリソース（最低限2 vCPU、4GB RAM、40GBディスク）を持つVM上にDocker Composeを展開する5。環境変数ファイル（.env）にAnthropicのAPIキー、Slackの各種トークン、およびホストのDockerソケット権限（DOCKER\_GID）を設定する5。  
2. **記憶アーキテクチャの実装**: CLAUDE.md やワークログファイルを用いたスレッド単位の短期記憶をローカルファイルシステムに構築する。同時に、Mem0のMCPサーバーをコンテナに組み込み、Slackから取得した user\_id を用いて、エージェントが記憶を書き込む際の名前空間を厳格に分離する23。  
3. **コンテキストルーティングの設定**: Slackのチャンネルと特定のプロジェクトディレクトリを紐付けるマッピング設定（projects.json 等）を導入し、複数人が異なるチャンネルで同時に作業を行っても、エージェントのコンテキストが交差しないようにする14。  
4. **プロンプトの最適化**: システムプロンプトを改修し、「Tool Search Tool」によるツール検索の強制、および「Programmatic Tool Calling」による大量データの分析手法を組み込むことで、コンテキストウィンドウの消費を最小限に抑える31。また、本番環境への影響を伴う操作に対しては、Slackのインタラクティブボタンを用いたHuman-in-the-loopの承認プロセスを挟むよう設計する17。

もし将来的に、スクレイピング専門、デザイン専門、コーディング専門といった複数の異なるエージェントを並行稼働させ、それらを同じSlackチャンネル内で連携させる必要が生じた場合には、OpenAgents WorkspaceのNetwork SDKを導入し、各エージェントのコンテキストを同期させるオーケストレーション層として機能させることが、アーキテクチャの自然な進化の道筋となるだろう32。

## **結論**

Claude Agent SDKを用いて、Docker上で動作しSlack経由で複数人がアクセス可能なパーソナルエージェントを構築するプロジェクトは、単なるAIツールの導入を超えた、企業の新しいナレッジマネジメント基盤の構築を意味する。

本分析によって明らかになったように、このシステムを成功に導くための鍵は、LLMの推論能力そのもの以上に、「実行環境の安全な隔離（Docker-out-of-Docker）」「セキュアな通信経路（Slack Socket Mode）」「認知科学に基づいたハイブリッド記憶アーキテクチャ（CLAUDE.mdによる短期記憶とMem0による長期ベクトル記憶）」、そして「コンテキストウィンドウを無駄にしない高度なプロンプトエンジニアリング（MCPツールの動的検索）」のシームレスな統合にある。

OpenAgents Workspaceはマルチエージェントのコラボレーションにおいて優れた概念を提供しているが、本プロジェクトの当面の要件に対しては、PhantomのようなClaude SDKに特化し、Slack連携と記憶基盤を最初から備えたOSSアーキテクチャをベースに開発を進めることが、最大の投資対効果と開発スピードをもたらす。これらのベストプラクティスを厳格に適用することで、組織の知識を継続的に学習し、セキュアな環境下で自律的にタスクを完遂する、真の「エージェンティック・コラボレーター」を本番環境で実現することが可能となる。

#### **引用文献**

1. Hosting the Agent SDK \- Claude API Docs, 4月 9, 2026にアクセス、 [https://platform.claude.com/docs/en/agent-sdk/hosting](https://platform.claude.com/docs/en/agent-sdk/hosting)  
2. Building an agentic Slackbot with Claude Code | by David Calvert | Medium, 4月 9, 2026にアクセス、 [https://medium.com/@dotdc/building-an-agentic-slackbot-with-claude-code-eba0e472d8f4](https://medium.com/@dotdc/building-an-agentic-slackbot-with-claude-code-eba0e472d8f4)  
3. Anthropic Claude SDK vs Dust: Build or use a platform?, 4月 9, 2026にアクセス、 [https://dust.tt/blog/anthropic-claude-sdk-vs-dust](https://dust.tt/blog/anthropic-claude-sdk-vs-dust)  
4. Connect MCP Servers to Claude Desktop with Docker MCP Toolkit, 4月 9, 2026にアクセス、 [https://www.docker.com/blog/connect-mcp-servers-to-claude-desktop-with-mcp-toolkit/](https://www.docker.com/blog/connect-mcp-servers-to-claude-desktop-with-mcp-toolkit/)  
5. ghostwright/phantom: An AI co-worker with its own ... \- GitHub, 4月 9, 2026にアクセス、 [https://github.com/ghostwright/phantom](https://github.com/ghostwright/phantom)  
6. Slackbot MCP Integration with Claude Agent SDK \- Composio, 4月 9, 2026にアクセス、 [https://composio.dev/toolkits/slackbot/framework/claude-agents-sdk](https://composio.dev/toolkits/slackbot/framework/claude-agents-sdk)  
7. punkpeye/awesome-mcp-servers: A collection of MCP servers. \- GitHub, 4月 9, 2026にアクセス、 [https://github.com/punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)  
8. How to Run Claude Code with Docker: Local Models, MCP Servers, and Secure Sandboxes, 4月 9, 2026にアクセス、 [https://www.docker.com/blog/run-claude-code-with-docker/](https://www.docker.com/blog/run-claude-code-with-docker/)  
9. The SRE Incident Response Agent, 4月 9, 2026にアクセス、 [https://platform.claude.com/cookbook/claude-agent-sdk-03-the-site-reliability-agent](https://platform.claude.com/cookbook/claude-agent-sdk-03-the-site-reliability-agent)  
10. How Coding Agents Work in Slack, 4月 9, 2026にアクセス、 [https://slack.com/blog/developers/coding-agents-in-slack](https://slack.com/blog/developers/coding-agents-in-slack)  
11. OpenClaw x Slack Workspace Integration Guide | MI \- 超智諮詢, 4月 9, 2026にアクセス、 [https://www.meta-intelligence.tech/en/insight-openclaw-slack](https://www.meta-intelligence.tech/en/insight-openclaw-slack)  
12. Setting Up OpenClaw AI Agents in Slack \- A Complete Walkthrough | Team 400 Blog, 4月 9, 2026にアクセス、 [https://team400.ai/blog/2026-03-openclaw-slack-integration-guide](https://team400.ai/blog/2026-03-openclaw-slack-integration-guide)  
13. Integrate OpenAI Agents SDK with Slack: Build an Agent to Operate Slack with Natural Language | by Astropomeai | Medium, 4月 9, 2026にアクセス、 [https://medium.com/@astropomeai/integrate-openai-agents-sdk-with-slack-build-an-agent-to-operate-slack-with-natural-language-f8f5144b566a](https://medium.com/@astropomeai/integrate-openai-agents-sdk-with-slack-build-an-agent-to-operate-slack-with-natural-language-f8f5144b566a)  
14. I made it so you can tag a bot in Slack and it runs Claude Code with full project context, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/ClaudeAI/comments/1sd3mo9/i\_made\_it\_so\_you\_can\_tag\_a\_bot\_in\_slack\_and\_it/](https://www.reddit.com/r/ClaudeAI/comments/1sd3mo9/i_made_it_so_you_can_tag_a_bot_in_slack_and_it/)  
15. Developing agents | Slack Developer Docs, 4月 9, 2026にアクセス、 [https://docs.slack.dev/ai/developing-agents/](https://docs.slack.dev/ai/developing-agents/)  
16. Templated MCP Integration with Claude Agent SDK \- Composio, 4月 9, 2026にアクセス、 [https://composio.dev/toolkits/templated/framework/claude-agents-sdk](https://composio.dev/toolkits/templated/framework/claude-agents-sdk)  
17. Comparison with Claude Agent SDK and Codex \- Docs by LangChain, 4月 9, 2026にアクセス、 [https://docs.langchain.com/oss/python/deepagents/comparison](https://docs.langchain.com/oss/python/deepagents/comparison)  
18. I got tired of creating Claude Code agents one by one, so I built an agent that designs entire teams — lessons from 35 generated teams : r/ClaudeAI \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/ClaudeAI/comments/1s6nk1p/i\_got\_tired\_of\_creating\_claude\_code\_agents\_one\_by/](https://www.reddit.com/r/ClaudeAI/comments/1s6nk1p/i_got_tired_of_creating_claude_code_agents_one_by/)  
19. AI agents need better memory systems, not just bigger context windows \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/AI\_Agents/comments/1r0q4qf/ai\_agents\_need\_better\_memory\_systems\_not\_just/](https://www.reddit.com/r/AI_Agents/comments/1r0q4qf/ai_agents_need_better_memory_systems_not_just/)  
20. Memory Types \- Mem0, 4月 9, 2026にアクセス、 [https://docs.mem0.ai/core-concepts/memory-types](https://docs.mem0.ai/core-concepts/memory-types)  
21. Prompting best practices \- Claude API Docs \- Claude Console, 4月 9, 2026にアクセス、 [https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)  
22. Best Practices for Claude Code, 4月 9, 2026にアクセス、 [https://code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices)  
23. Add Persistent Memory to Claude Code with Mem0 (5-Minute Setup), 4月 9, 2026にアクセス、 [https://mem0.ai/blog/claude-code-memory](https://mem0.ai/blog/claude-code-memory)  
24. I built a self-hosted mem0 MCP memory server for Claude Code that gives persistent memory across sessions with local Qdrant \+ Neo4j \+ Ollama : r/ClaudeAI \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/ClaudeAI/comments/1r6r87z/i\_built\_a\_selfhosted\_mem0\_mcp\_memory\_server\_for/](https://www.reddit.com/r/ClaudeAI/comments/1r6r87z/i_built_a_selfhosted_mem0_mcp_memory_server_for/)  
25. Best AI Agent Memory Frameworks 2026: Mem0, Zep, LangChain, Letta \- Atlan, 4月 9, 2026にアクセス、 [https://atlan.com/know/best-ai-agent-memory-frameworks-2026/](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)  
26. What Is Agent Memory Infrastructure? How Mem0 Beats OpenAI's Built-In Memory by 26%, 4月 9, 2026にアクセス、 [https://www.mindstudio.ai/blog/agent-memory-infrastructure-mem0-vs-openai](https://www.mindstudio.ai/blog/agent-memory-infrastructure-mem0-vs-openai)  
27. How to give Claude Code persistent memory with a self-hosted mem0 MCP server, 4月 9, 2026にアクセス、 [https://dev.to/n3rdh4ck3r/how-to-give-claude-code-persistent-memory-with-a-self-hosted-mem0-mcp-server-h68](https://dev.to/n3rdh4ck3r/how-to-give-claude-code-persistent-memory-with-a-self-hosted-mem0-mcp-server-h68)  
28. Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory \- arXiv, 4月 9, 2026にアクセス、 [https://arxiv.org/abs/2504.19413](https://arxiv.org/abs/2504.19413)  
29. AI Memory Systems Benchmark: Mem0 vs OpenAI vs LangMem 2025 \- Deepak Gupta, 4月 9, 2026にアクセス、 [https://guptadeepak.com/the-ai-memory-wars-why-one-system-crushed-the-competition-and-its-not-openai/](https://guptadeepak.com/the-ai-memory-wars-why-one-system-crushed-the-competition-and-its-not-openai/)  
30. Group Chat \- Mem0 Docs, 4月 9, 2026にアクセス、 [https://docs.mem0.ai/platform/features/group-chat](https://docs.mem0.ai/platform/features/group-chat)  
31. Introducing advanced tool use on the Claude Developer ... \- Anthropic, 4月 9, 2026にアクセス、 [https://www.anthropic.com/engineering/advanced-tool-use](https://www.anthropic.com/engineering/advanced-tool-use)  
32. openagents-org/openagents: OpenAgents \- AI Agent ... \- GitHub, 4月 9, 2026にアクセス、 [https://github.com/openagents-org/openagents](https://github.com/openagents-org/openagents)  
33. Slack for AI Agents: Shared Memory, Context, and Workflows Between Multiple Agents : r/vibecoding \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/vibecoding/comments/1sf12nw/slack\_for\_ai\_agents\_shared\_memory\_context\_and/](https://www.reddit.com/r/vibecoding/comments/1sf12nw/slack_for_ai_agents_shared_memory_context_and/)  
34. I gave Claude its own computer and let it run 24/7. Here's what it built. : r/ClaudeAI \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/ClaudeAI/comments/1s84l18/i\_gave\_claude\_its\_own\_computer\_and\_let\_it\_run\_247/](https://www.reddit.com/r/ClaudeAI/comments/1s84l18/i_gave_claude_its_own_computer_and_let_it_run_247/)  
35. OpenClaw Slack Workflow Automation Deployment Tutorial \- Tencent Cloud, 4月 9, 2026にアクセス、 [https://www.tencentcloud.com/techpedia/139508](https://www.tencentcloud.com/techpedia/139508)  
36. Integrate AgentCore Memory with LangChain or LangGraph \- AWS Documentation, 4月 9, 2026にアクセス、 [https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html)  
37. Comparing Open-Source AI Agent Frameworks \- Langfuse, 4月 9, 2026にアクセス、 [https://langfuse.com/blog/2025-03-19-ai-agent-comparison](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)  
38. Stopped choosing between LangGraph and Claude SDK \- using both solved my multi-agent headaches : r/LangChain \- Reddit, 4月 9, 2026にアクセス、 [https://www.reddit.com/r/LangChain/comments/1qg98n5/stopped\_choosing\_between\_langgraph\_and\_claude\_sdk/](https://www.reddit.com/r/LangChain/comments/1qg98n5/stopped_choosing_between_langgraph_and_claude_sdk/)