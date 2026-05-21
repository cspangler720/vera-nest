from typing import Callable

import numpy as np


def genetc_loop(gene, target_fitness_value, fit_func):
    population = gene
    generation = 0
    max_generations = 100

    while True:
        fitness_values = fitness(population, fit_func)
        sorted_population = sort_by_fitness(population, fitness_values)

        best_fitness = max(fitness_values)

        if generation >= max_generations:
            break

        if best_fitness >= target_fitness_value:
            break

        if len(fitness_values) > 10:
            recent = fitness_values[-10:]
            if max(recent) - min(recent) < 1e-6:
                break

        new_population = []

        elite_count = max(2, len(sorted_population) // 10)
        new_population.extend(sorted_population[:elite_count])

        while len(new_population) < len(sorted_population):
            parents = np.random.choice(sorted_population[:len(sorted_population)//2], 2, replace=False)
            child = crossover(parents[0], parents[1])
            child = mutate(child)
            new_population.append(child)

        population = new_population
        generation += 1

    return population


def crossover(a1: np.array, a2: np.array) -> np.array:
    x = np.random.randint(1, a1.size)
    # Source - https://stackoverflow.com/a/41193427
    # Posted by Divakar, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-05-20, License - CC BY-SA 3.0
    tmp = a2[:x].copy()
    a2[:x], a1[:x]  = a1[:x], tmp
    return a2

def normalize(list :list[float]) -> list[float]:
    coef = 1 / max(list)
    return [val * coef for val in list]


def initalize_genes(candidates: list, inital_population: int) -> list:
    population = []
    for i in range(inital_population):
        population.append(candidates[np.random.randint(0, len(candidates))])
    return population


def fitness(genes: list, fit_func: Callable[[np.ndarray], float]) -> list[float]:
    return [fit_func(g) for g in genes]


def sort_by_fitness(genes: list, fitness_values: list[float]) -> list:
    paired = list(zip(genes, fitness_values))
    paired.sort(key=lambda x: x[1], reverse=True)
    return [g for g, _ in paired]


def select(genes: list, percent_to_keep: float) -> list:
    fitness_values = fitness(genes)
    sorted_genes = sort_by_fitness(genes, fitness_values)
    cutoff = max(1, int(len(sorted_genes) * percent_to_keep))
    return sorted_genes[:cutoff]


def mutate(gene: np.array, mutation_rate: float = 0.1) -> np.array:
    mutated = gene.copy()

    for i in range(mutated.size):
        if np.random.rand() < mutation_rate:
            # small random change
            mutated[i] += np.random.normal(0, 1)

    return mutated


def reproduce(population: list, mutation_rate: float = 0.1) -> list:
    new_population = []

    fitness_values = fitness(population)
    population = sort_by_fitness(population, fitness_values)

    # elitism: keep top 2
    elite_count = max(2, len(population) // 10)
    new_population.extend(population[:elite_count])

    # generate rest
    while len(new_population) < len(population):
        parents = np.random.choice(population[:len(population)//2], 2, replace=False)
        child = crossover(parents[0], parents[1])
        child = mutate(child, mutation_rate)
        new_population.append(child)

    return new_population


def terminate(population: list, generation: int,
                max_generations: int = 100,
                target_fitness: float = None) -> bool:

    fitness_values = fitness(population)
    best = max(fitness_values)

    if generation >= max_generations:
        return True

    if target_fitness is not None and best >= target_fitness:
        return True

    # optional stagnation check
    if len(fitness_values) > 10:
        recent = fitness_values[-10:]
        if max(recent) - min(recent) < 1e-6:
            return True

    return False


def _example():
    import numpy as np

    def example_fitness_func(x: np.ndarray) -> float:
        return float(np.sum(x))

    inital_candidates = [
        np.random.uniform(-5, 5, size=5)
        for _ in range(20)
    ]

    population = initalize_genes(inital_candidates, inital_population=30)

    final_population = genetc_loop(
        gene=population,
        target_fitness_value=15.0,
        fit_func=example_fitness_func
    )

    # Evaluate final results
    final_scores = fitness(final_population, example_fitness_func)

    best_index = int(np.argmax(final_scores))
    best_gene = final_population[best_index]

    print(f"Best gene: {best_gene}")
    print(f"Best fitness: {final_scores}")

if __name__ == '__main__':
    _example()