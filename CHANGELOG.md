# CHANGELOG

<!-- version list -->

## v3.1.0 (2026-03-02)

### Bug Fixes

- **installer**: Add filter parameter to tarfile extraction for security
  ([`5668de9`](https://github.com/edu526/devo-cli/commit/5668de923e3093bced4910172e64ebb0cb479d4e))

### Chores

- **ci**: Move unit tests to pre-push hook and add Python 3.13 support
  ([`d6d1ce4`](https://github.com/edu526/devo-cli/commit/d6d1ce47f113112772d49bca909111bd1db337d5))

- **deps**: Add pytest-cov and moto to dev dependencies
  ([`2ca6f89`](https://github.com/edu526/devo-cli/commit/2ca6f89b3a8ee18086586ca6d7fffbb514a1beda))

- **isort**: Exclude _version.py from import sorting
  ([`c7ae150`](https://github.com/edu526/devo-cli/commit/c7ae15087df49fb6750589db6fd951cae6ca0ba6))

- **makefile**: Consolidate install targets and simplify dependency management
  ([`92d0f10`](https://github.com/edu526/devo-cli/commit/92d0f10ac115c31521c22632b6671904382aedf3))

### Code Style

- Normalize code formatting and pre-commit hook stages
  ([`eac95bb`](https://github.com/edu526/devo-cli/commit/eac95bbc81518fd315fa9ecd604bd9b83d96fd40))

### Continuous Integration

- Add Codecov token secret passing to workflows
  ([`02be0b0`](https://github.com/edu526/devo-cli/commit/02be0b00807a469789783e7eba73511ee0cad356))

- Add lint job dependency to test workflows
  ([`9b5d637`](https://github.com/edu526/devo-cli/commit/9b5d637ec4f73d84d2edf718088acc482e43d95b))

- Adjust CI/CD configuration and test coverage thresholds
  ([`c2baad8`](https://github.com/edu526/devo-cli/commit/c2baad8ce54f2a43bf52d60626f7a7a8e88dcd55))

- Adjust coverage threshold and improve coverage configuration
  ([`18f9dce`](https://github.com/edu526/devo-cli/commit/18f9dceba1d6fc59bd778f40ca53f1783de8a945))

- Expand test matrix and refactor workflows for multi-platform coverage
  ([`e2c889d`](https://github.com/edu526/devo-cli/commit/e2c889db9d72fc7afdb3f6acd33a2a350e6f3d16))

- Install package in editable mode for development workflows
  ([`fa7ef9e`](https://github.com/edu526/devo-cli/commit/fa7ef9efd5ad850fbff0d97a125a79e63bccc28c))

- Optimize CI/CD workflows with pip caching and dependency groups
  ([`4752f8c`](https://github.com/edu526/devo-cli/commit/4752f8cd5cdb5b8de70ecca4b102609e8ae71f05))

- Refactor workflows with reusable lint job and matrix strategy
  ([`ba11537`](https://github.com/edu526/devo-cli/commit/ba115378cf2f4f72821ab8cc08343ae9d68c9e8b))

- Update macOS runner from macos-14-large to macos-15-intel
  ([`a4513bb`](https://github.com/edu526/devo-cli/commit/a4513bb34b08d570d926d34c5cbe79fb3627173a))

- **test-reusable**: Enhance test workflow with improved coverage reporting
  ([`272d019`](https://github.com/edu526/devo-cli/commit/272d0199232f83c5023d2f2ec841e6022d246181))

### Documentation

- Add architecture documentation and command READMEs
  ([`9a20541`](https://github.com/edu526/devo-cli/commit/9a205416c6768f6bee1e8e0ddb7df2085f7ef48a))

- **commands**: Update module paths to reflect unified commands directory
  ([`31b466a`](https://github.com/edu526/devo-cli/commit/31b466a1613bb44ff28ffadf583e02c938a872cf))

### Features

- **ssm**: Enhance database connection display with rich table formatting
  ([`a2f5ab0`](https://github.com/edu526/devo-cli/commit/a2f5ab0529f00c038afdc6a7aed025e9de91f1af))

### Refactoring

- **autocomplete**: Restructure into modular command and core architecture
  ([`4560759`](https://github.com/edu526/devo-cli/commit/4560759f9f0e592bc3a074df6e202fcf8c36e314))

- **aws-login**: Restructure into modular command and core architecture
  ([`5594a9b`](https://github.com/edu526/devo-cli/commit/5594a9b913f9d22fe89ebf61b381d7eec1339285))

- **cli**: Consolidate command modules under unified commands directory
  ([`4f7d479`](https://github.com/edu526/devo-cli/commit/4f7d47903a876ed9b99e2acbaf4ed076b1ebc46e))

- **cli**: Eliminate thin wrapper layer in cli_tool/commands/
  ([`cf35933`](https://github.com/edu526/devo-cli/commit/cf35933e6c271feddffd6f09bec86b0c87c3ed57))

- **code_reviewer**: Restructure into modular command and core architecture
  ([`4c61124`](https://github.com/edu526/devo-cli/commit/4c6112468c1b047904b7dddc13e3034c0300db69))

- **code_reviewer, dynamodb**: Restructure into modular command and core architecture
  ([`4628df4`](https://github.com/edu526/devo-cli/commit/4628df4f96daae84140c007257fc56a623caf75f))

- **codeartifact**: Restructure into modular command and core architecture
  ([`2a41211`](https://github.com/edu526/devo-cli/commit/2a41211c6c7cbf4acd2417906b0d509f71fa6904))

- **commit**: Restructure into modular command and core architecture
  ([`584a21d`](https://github.com/edu526/devo-cli/commit/584a21de801bd7910c08370eac5f44a80d017cae))

- **config**: Restructure into modular command and core architecture
  ([`432b24e`](https://github.com/edu526/devo-cli/commit/432b24ef274be8903dcb4455bbb16fa8c061a02b))

- **core**: Add explicit exports to agent and utils modules
  ([`73774d5`](https://github.com/edu526/devo-cli/commit/73774d5b4cfbc541e28a655822f9cbc6a5132c6b))

- **dynamodb**: Restructure into modular command and core architecture
  ([`cf58ba1`](https://github.com/edu526/devo-cli/commit/cf58ba1708a425919f0168cdd1e279e4022d5a5d))

- **eventbridge**: Restructure into modular command and core architecture
  ([`0e34093`](https://github.com/edu526/devo-cli/commit/0e34093f10d4360119d4bea44765c7b1bf31ec6b))

- **ssm**: Restructure into modular command architecture
  ([`0264ceb`](https://github.com/edu526/devo-cli/commit/0264cebb39de89d731ea0fb6e63836168e14143a))

- **upgrade**: Restructure into modular command and core architecture
  ([`2bbb19b`](https://github.com/edu526/devo-cli/commit/2bbb19bbc73653689a7971928d90604dddd2a7b8))

### Testing

- Add comprehensive test suite with fixtures and CI/CD improvements
  ([`c5d8f05`](https://github.com/edu526/devo-cli/commit/c5d8f0520a94a097385e2c4596abcd9191c49972))

- Expand test suite with error handling, integration, and regression tests
  ([`a28344e`](https://github.com/edu526/devo-cli/commit/a28344e4b0fd48d7c65aac46c3d355f71794eec3))

- Improve cross-platform test reliability and Windows mocking
  ([`a245849`](https://github.com/edu526/devo-cli/commit/a245849a68cb30db998d96134b1f929f582fd0e1))

- **aws_login**: Add comprehensive test suite for list profiles command
  ([`f5f4697`](https://github.com/edu526/devo-cli/commit/f5f469749e8bde2ce3114711077fb051a62bfda1))


## v3.0.0 (2026-03-02)

### Bug Fixes

- **commit-prompt**: Ensure context object initialization before profile selection
  ([`4d44b1c`](https://github.com/edu526/devo-cli/commit/4d44b1ca902b8938052652e18ebd11e3b12c7bf2))

### Continuous Integration

- **docs**: Refactor GitHub Pages deployment workflow
  ([`8152cd2`](https://github.com/edu526/devo-cli/commit/8152cd2f011084c5da31233adc07589957f32a2f))

### Documentation

- **config**: Restructure command documentation with consolidated sections
  ([`0531e9a`](https://github.com/edu526/devo-cli/commit/0531e9aee450f7d692ea7b63068705c58d32724e))

### Features

- **aws-login**: Enhance profile discovery with source tracking
  ([`d6249cf`](https://github.com/edu526/devo-cli/commit/d6249cf99427db47f2d3e74dc88487be3f468085))

### Refactoring

- **aws**: Move profile selection to command level
  ([`2389143`](https://github.com/edu526/devo-cli/commit/2389143824ec20d7c643ff7c6bae97f9c93a9f71))

- **commit-prompt**: Move select_profile import to module level
  ([`fe3b216`](https://github.com/edu526/devo-cli/commit/fe3b2164298777d30d90ab216def8bfb631ed6e8))

### Testing

- **commit-prompt**: Mock select_profile in no staged changes test
  ([`c1f6620`](https://github.com/edu526/devo-cli/commit/c1f66207912c8ee7ed278dad8f8ddb36346cc8e0))


## v2.7.0 (2026-03-01)

### Continuous Integration

- **release**: Refine artifact filtering in release workflow
  ([`8033ac8`](https://github.com/edu526/devo-cli/commit/8033ac89a64dcd2db487436bd49fef33425f6661))

### Documentation

- **aws-login**: Add set-default profile documentation
  ([`2b3ee4a`](https://github.com/edu526/devo-cli/commit/2b3ee4aa20fdba567c73e3bb659598cbfe60753c))

### Features

- **aws-login**: Add AWS SSO authentication and credential management
  ([`2b7860c`](https://github.com/edu526/devo-cli/commit/2b7860c0028c654bcf9b83bbf889e79ec20fa5bd))

- **aws-login**: Add Windows environment variable support for default profile
  ([`bd95f05`](https://github.com/edu526/devo-cli/commit/bd95f054a432031fcbc3f610e745aa9c304fe8d1))


## v2.6.0 (2026-02-27)

### Code Style

- **install**: Remove trailing whitespace
  ([`da51b3a`](https://github.com/edu526/devo-cli/commit/da51b3a19bdd2515469dfed7b83e5e8b36d2c615))

### Features

- **install**: Add macOS tarball support and improve cross-platform installation
  ([`81b713f`](https://github.com/edu526/devo-cli/commit/81b713f3415c8e20cf214ce7b245443f315e33f6))


## v2.5.0 (2026-02-27)

### Code Style

- Remove trailing whitespace across build and docs files
  ([`f78b679`](https://github.com/edu526/devo-cli/commit/f78b67999a7156ba5c04962e6780b11786ed4df5))

### Features

- **build**: Support macOS onedir binary format and improve cross-platform packaging
  ([`d9a00a3`](https://github.com/edu526/devo-cli/commit/d9a00a305cd942cda5f32d7a1bb815180374a964))


## v2.4.0 (2026-02-26)

### Documentation

- Restructure command documentation and add workflow guides
  ([`dadd873`](https://github.com/edu526/devo-cli/commit/dadd8732591dc15fb6efcb091aff970f6dae2a34))

### Features

- **ssm**: Add macOS loopback alias management and improve error handling
  ([`8827d26`](https://github.com/edu526/devo-cli/commit/8827d265c2accf83bb939717681e44f575cca5ea))


## v2.3.3 (2026-02-26)

### Bug Fixes

- **ssm**: Implement unique local port allocation to prevent conflicts
  ([`6fe4b58`](https://github.com/edu526/devo-cli/commit/6fe4b58284d46af3b9b37049ac029a830d067369))


## v2.3.2 (2026-02-26)

### Bug Fixes

- **ssm**: Replace multiprocessing with threading for port forwarding
  ([`5c5f08c`](https://github.com/edu526/devo-cli/commit/5c5f08c33656cf603c47d8a5163d6c5922a1a306))

### Code Style

- **ssm**: Remove trailing whitespace and fix formatting
  ([`02c4bd4`](https://github.com/edu526/devo-cli/commit/02c4bd47a51bcd705f2a3b9993b8851c9abd7245))


## v2.3.1 (2026-02-26)

### Bug Fixes

- **ssm**: Set multiprocessing start method for Windows compatibility
  ([`e594fba`](https://github.com/edu526/devo-cli/commit/e594fba0cc8c6cc13191c9c2da0982bd8ea99700))


## v2.3.0 (2026-02-25)

### Bug Fixes

- **ssm**: Add plugin validation and improve error handling
  ([`720a375`](https://github.com/edu526/devo-cli/commit/720a375224bfb3b3f9fa506b024630f27158b8b4))

- **ssm**: Capture and handle port forwarding exit codes
  ([`bf58965`](https://github.com/edu526/devo-cli/commit/bf58965fee2ac6cc3f9754ef8c88f2dca0b4e148))

- **ssm**: Capture output and improve error handling for missing plugin
  ([`7648ef2`](https://github.com/edu526/devo-cli/commit/7648ef2f4120f72295f9c41d99d6caab845d3331))

- **ssm**: Remove captured output to enable real-time feedback
  ([`4f83d20`](https://github.com/edu526/devo-cli/commit/4f83d20f88c23308b045dcbd011f3b421ee57919))

- **ssm,cli**: Improve hosts setup feedback and remove unused admin check
  ([`40b73b9`](https://github.com/edu526/devo-cli/commit/40b73b9eec2e5875b6abf029c075c924fa69e10e))

- **ssm,docs**: Improve Windows compatibility and activation instructions
  ([`261354e`](https://github.com/edu526/devo-cli/commit/261354e45f193445e2feb3f147a09218dc3f4706))

### Chores

- **makefile**: Improve Windows venv setup with better feedback
  ([`9b0c81a`](https://github.com/edu526/devo-cli/commit/9b0c81a14e70eda4b1a8e96a2a2cffb3542c7030))

- **spec**: Add hidden imports for dynamodb and ssm modules
  ([`d64dc7e`](https://github.com/edu526/devo-cli/commit/d64dc7eff0a1dfe768b3c7a6294c6a10d50d1d60))

### Continuous Integration

- Optimize workflows to skip tests/release on docs changes
  ([`c29e59d`](https://github.com/edu526/devo-cli/commit/c29e59dd31e25c99f2dd869ebb3f349d53284447))

- **docs**: Improve GitHub Pages deployment workflow and add documentation badge
  ([`1e091ab`](https://github.com/edu526/devo-cli/commit/1e091ab0a9a1a1774997f584d62ad7da24204d7b))

### Documentation

- Add status and metadata badges to README
  ([`84f250a`](https://github.com/edu526/devo-cli/commit/84f250a6b20df1ddb96f8b00d967b39a8d1b1446))

- **ssm**: Expand requirements and improve architecture documentation
  ([`1d5fd65`](https://github.com/edu526/devo-cli/commit/1d5fd6557ee1ae0443fcd65904c9bfd587c899ce))

### Features

- **ssm**: Add AWS Systems Manager Session Manager integration
  ([`1c23477`](https://github.com/edu526/devo-cli/commit/1c2347776e6ebe9e85baf73c9ad77694f39312c3))


## v2.2.0 (2026-02-25)

### Documentation

- Restructure documentation with mkdocs and automated deployment
  ([`6ae7c0f`](https://github.com/edu526/devo-cli/commit/6ae7c0fb8a02ead2fe88b174a3fc56451cbdfa92))

### Features

- **completion**: Add automatic shell completion setup with --install flag
  ([`47a244d`](https://github.com/edu526/devo-cli/commit/47a244dc81430b4574f4ce66f112f6cd4fc2af00))


## v2.1.0 (2026-02-25)

### Features

- **dynamodb**: Add DynamoDB table management and export utilities
  ([`a27fd2f`](https://github.com/edu526/devo-cli/commit/a27fd2ff636663fb4a41c36cbf28db85b477cabe))


## v2.0.3 (2026-02-23)

### Bug Fixes

- Correct Windows upgrade subprocess flags
  ([`c0123a2`](https://github.com/edu526/devo-cli/commit/c0123a2ffc3633dd3d2713767512ccc681527c31))


## v2.0.2 (2026-02-23)

### Bug Fixes

- **build**: Improve cross-platform setup and upgrade experience
  ([`933040a`](https://github.com/edu526/devo-cli/commit/933040aaa1a9b5cf610abd91322da5031ff2a4f1))


## v2.0.1 (2026-02-23)

### Bug Fixes

- Align release workflow after v2.0.0
  ([`371ebf9`](https://github.com/edu526/devo-cli/commit/371ebf92f7768474590f04ab233cdacf21504ec9))

### Refactoring

- **upgrade**: Simplify Windows binary replacement logic
  ([`5ec3c80`](https://github.com/edu526/devo-cli/commit/5ec3c80ca6b39c05ec11b4d2ca2798d70e577aa2))


## v2.0.0 (2026-02-23)

### Chores

- Remove jinja2 dependency and template-related code
  ([`0f9ce52`](https://github.com/edu526/devo-cli/commit/0f9ce52bcf64910a29a52adce92bf2fba4b72441))

### Continuous Integration

- Remove path filters from release and test workflows
  ([`d5f1a9e`](https://github.com/edu526/devo-cli/commit/d5f1a9e792f6d48a59f4a0d93f0db9dec3699202))

- **release**: Add duplicate tag detection and Windows support
  ([`809b8a9`](https://github.com/edu526/devo-cli/commit/809b8a9ec83d26be168e486e0060504baa7b2a76))

- **release**: Improve tag handling and workflow structure
  ([`59c1930`](https://github.com/edu526/devo-cli/commit/59c19307db626188fd2ee2ae5fbea2c7c67b4fdc))

### Documentation

- **changelog**: Reorganize release history and add v1.1.0-v1.2.0 entries
  ([`560ace4`](https://github.com/edu526/devo-cli/commit/560ace41be3efe35d1bbf7d8f1711295bb274f46))

### Features

- Remove generate command and clean up dependencies
  ([`e03713a`](https://github.com/edu526/devo-cli/commit/e03713a5a7b8e8050153b36ec0b9d1724e5e451a))

### Refactoring

- Remove template-based code generation feature
  ([`1a484fc`](https://github.com/edu526/devo-cli/commit/1a484fc702b67d08ce2ab8fc28748d84f7d7ba7f))

### Breaking Changes

- The 'devo generate' command has been removed


## v1.2.0 (2026-02-20)

### Features

- **upgrade**: Add binary verification and improve backup handling
  ([`ff46993`](https://github.com/edu526/devo-cli/commit/ff46993949bd997fd4d4dc8a3d1393baa64d8382))


## v1.1.1 (2026-02-20)

### Bug Fixes

- **config**: Replace err parameter with style for console output
  ([`e80d76c`](https://github.com/edu526/devo-cli/commit/e80d76ca1dacc6cd84ed9908a7ee16bfcb398c41))


## v1.1.0 (2026-02-20)

### Features

- **config**: Add configuration management system with CLI commands
  ([`ac325d6`](https://github.com/edu526/devo-cli/commit/ac325d612c3a6670bbd4615f531d712513740079))

- **upgrade**: Migrate to GitHub releases and add automatic version checking
  ([`a2ff069`](https://github.com/edu526/devo-cli/commit/a2ff069ae36f94fe332090fa9778d26c8b94ca09))

### Documentation

- Reorganize README structure and improve formatting
  ([`7e4f493`](https://github.com/edu526/devo-cli/commit/7e4f493ca0a8b7d18174ab42268069ba9796b6ab))

### Chores

- **.gitignore**: Add config file patterns to gitignore
  ([`6c22c24`](https://github.com/edu526/devo-cli/commit/6c22c24efff0f9c59a2d21ee8eca16d01af6774e))

### Refactoring

- **config**: Clean up imports and remove unused variables
  ([`300df2b`](https://github.com/edu526/devo-cli/commit/300df2bc6b9417e4db44c97ceedcd4ffae3f04c0))


## v1.0.6 (2026-02-21)

### Bug Fixes

- **build**: Keep required stdlib modules for PyInstaller runtime
  ([`7a58359`](https://github.com/edu526/devo-cli/commit/7a58359dfc851caaa9bec3b01104c8264de90997))


## v1.0.5 (2026-02-21)

### Performance Improvements

- **build**: Optimize Windows binary startup performance
  ([`bd812df`](https://github.com/edu526/devo-cli/commit/bd812dfd752983c0467454048bd539e862a1d301))


## v1.0.4 (2026-02-21)

### Bug Fixes

- **build**: Install dependencies before building Windows binary
  ([`26c0ff0`](https://github.com/edu526/devo-cli/commit/26c0ff01a55f60e18cd5f1a28609d903bf605707))


## v1.0.3 (2026-02-21)

### Bug Fixes

- **build**: Add copy_metadata for rich to fix Windows PyInstaller issue
  ([`7eab4c1`](https://github.com/edu526/devo-cli/commit/7eab4c1bb07e1b106c2ac8e83da54772b09ecde8))


## v1.0.2 (2026-02-21)

### Bug Fixes

- **build**: Make git imports lazy to avoid initialization errors
  ([`02e22bc`](https://github.com/edu526/devo-cli/commit/02e22bc4305ce19bad6c0bb9ede7b6b1874f34ac))


## v1.0.1 (2026-02-21)

### Bug Fixes

- **build**: Explicitly list rich modules in PyInstaller spec
  ([`c0002bd`](https://github.com/edu526/devo-cli/commit/c0002bdedd8facf39304337585e3a9a32ab207a8))


## v1.0.0 (2026-02-21)

- Initial Release
