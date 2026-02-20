# Language Guidelines

## Code and Documentation Language

**All code, comments, documentation, and files MUST be written in English.**

This includes:

- Source code (variables, functions, classes, methods)
- Code comments and documentation
- Commit messages
- README files and documentation
- Configuration files
- Test descriptions
- Error messages
- Log messages
- API responses
- User-facing text in applications

## Why English?

- **Universal standard**: English is the lingua franca of software development
- **Collaboration**: Enables collaboration with international developers
- **Tooling**: Most development tools, libraries, and frameworks use English
- **Maintainability**: Makes code easier to maintain and understand globally
- **Best practice**: Industry standard for professional software development

## Examples

### ✅ Correct (English)

```typescript
// Calculate the total price including tax
function calculateTotalPrice(subtotal: number, taxRate: number): number {
  return subtotal * (1 + taxRate);
}

const userEmail = "user@example.com";
const isAuthenticated = true;
```

### ❌ Incorrect (Spanish or other languages)

```typescript
// Calcular el precio total incluyendo impuestos
function calcularPrecioTotal(subtotal: number, tasaImpuesto: number): number {
  return subtotal * (1 + tasaImpuesto);
}

const correoUsuario = "usuario@ejemplo.com";
const estaAutenticado = true;
```

## Exceptions

The only acceptable exceptions are:

- Content specifically intended for non-English users (e.g., translations, i18n files)
- Business domain terms that must remain in the original language
- Proper nouns and brand names

## Enforcement

- Code reviews should reject any code with non-English identifiers or comments
- Linters and formatters should be configured to enforce English naming conventions
- Documentation should be written in clear, professional English
