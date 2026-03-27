export function titleCase(s: string): string {
    return s
        .split(' ')
        .map(word => {
            if (word.length === 0) return word;
            return word[0].toUpperCase() + word.slice(1).toLowerCase();
        })
        .join(' ');
}