import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/components/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [
          {
            group: ['**/api/client', '**/api/client.*', '../api/client', '../../api/client', '../../../api/client'],
            message: 'Components must not import from src/api/client directly. Use src/queries/ hooks instead.',
          },
        ],
      }],
    },
  },
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
);
