# CHANGELOG

<!-- version list -->

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

## v1.0.0 (2026-02-20)

- Initial Release

## v1.3.0 (2026-02-20)

### Features

- **cli**: Add EventBridge command and improve AWS profile handling
  ([`0c43719`](https://github.com/edu526/devo-cli/commit/0c43719a325503153de5de38ae0a8f03a1d1059a))

### Refactoring

- **cli**: Clean up imports and formatting
  ([`4de3cae`](https://github.com/edu526/devo-cli/commit/4de3cae0a0a7cbd7d7963133014c757996dcbd77))


## v1.2.2 (2026-02-20)

### Bug Fixes

- **upgrade**: Improve temp file cleanup and process termination
  ([`1ca5656`](https://github.com/edu526/devo-cli/commit/1ca56568ef19956d8066ff044fc51846531f4fae))

### Continuous Integration

- **release**: Add Telegram notifications for release workflow
  ([`221d886`](https://github.com/edu526/devo-cli/commit/221d886bbcd81a33747da85b9624b67d29b360ed))

- **release**: Improve Telegram notification reliability and error handling
  ([`ae447c9`](https://github.com/edu526/devo-cli/commit/ae447c92c1c075e0c150f85060acff8fda6020c3))

- **release**: Improve Telegram notification robustness
  ([`d923595`](https://github.com/edu526/devo-cli/commit/d923595ef15eaaf4f126cd8aee79f705b5b1bfdf))


## v1.2.1 (2026-02-20)

### Bug Fixes

- **cli**: Skip AWS credential check for commands that don't require it
  ([`c0d69b8`](https://github.com/edu526/devo-cli/commit/c0d69b8b921e73b9ef5692d6fb094208c96b0975))


## v1.2.0 (2026-02-20)

### Features

- **upgrade**: Add binary verification and improve backup handling
  ([`ff46993`](https://github.com/edu526/devo-cli/commit/ff46993949bd997fd4d4dc8a3d1393baa64d8382))


## v1.1.1 (2026-02-20)

### Bug Fixes

- **config**: Replace err parameter with style for console output
  ([`e80d76c`](https://github.com/edu526/devo-cli/commit/e80d76ca1dacc6cd84ed9908a7ee16bfcb398c41))


## v1.1.0 (2026-02-20)

### Chores

- **.gitignore**: Add config file patterns to gitignore
  ([`6c22c24`](https://github.com/edu526/devo-cli/commit/6c22c24efff0f9c59a2d21ee8eca16d01af6774e))

### Documentation

- Reorganize README structure and improve formatting
  ([`7e4f493`](https://github.com/edu526/devo-cli/commit/7e4f493ca0a8b7d18174ab42268069ba9796b6ab))

### Features

- **config**: Add configuration management system with CLI commands
  ([`ac325d6`](https://github.com/edu526/devo-cli/commit/ac325d612c3a6670bbd4615f531d712513740079))

- **upgrade**: Migrate to GitHub releases and add automatic version checking
  ([`a2ff069`](https://github.com/edu526/devo-cli/commit/a2ff069ae36f94fe332090fa9778d26c8b94ca09))

### Refactoring

- **config**: Clean up imports and remove unused variables
  ([`300df2b`](https://github.com/edu526/devo-cli/commit/300df2bc6b9417e4db44c97ceedcd4ffae3f04c0))


## v1.0.0 (2026-02-20)

- Initial Release
