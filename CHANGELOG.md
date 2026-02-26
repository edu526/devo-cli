# CHANGELOG

<!-- version list -->

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
