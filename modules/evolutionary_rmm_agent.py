"""
🧬 Эволюционный агент управления рисками и деньгами (RMM)
Заглушка для совместимости
"""

class EvolutionaryRMMAgent:
    """Эволюционный агент для управления рисками и деньгами"""
    
    def __init__(self, population_size=20, mutation_rate=0.2, elite_frac=0.2):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.elite_frac = elite_frac
        self.population = []
        self.generation = 0
        self.best_fitness = 0.0
        self.best_individual = None
        
        # Инициализация популяции
        self._initialize_population()
    
    def _initialize_population(self):
        """Инициализация начальной популяции"""
        for _ in range(self.population_size):
            individual = {
                'risk_per_trade': 0.01 + 0.02 * (0.5 - 0.5),  # 1-3%
                'max_positions': 3,
                'stop_loss': 0.02,  # 2%
                'take_profit': 0.04,  # 4%
                'leverage': 3.0,
                'confidence_threshold': 0.35
            }
            self.population.append(individual)
    
    def evolve(self, fitness_scores):
        """Эволюция популяции на основе фитнес-оценок"""
        if len(fitness_scores) != len(self.population):
            return
        
        # Сортируем по фитнесу
        sorted_population = [x for _, x in sorted(zip(fitness_scores, self.population), reverse=True)]
        
        # Отбираем элиту
        elite_size = int(self.population_size * self.elite_frac)
        elite = sorted_population[:elite_size]
        
        # Создаем новое поколение
        new_population = elite.copy()
        
        # Дополняем популяцию потомками
        while len(new_population) < self.population_size:
            parent1 = self._select_parent(sorted_population, fitness_scores)
            parent2 = self._select_parent(sorted_population, fitness_scores)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            new_population.append(child)
        
        self.population = new_population
        self.generation += 1
        
        # Обновляем лучшего индивида
        if fitness_scores:
            best_idx = fitness_scores.index(max(fitness_scores))
            if fitness_scores[best_idx] > self.best_fitness:
                self.best_fitness = fitness_scores[best_idx]
                self.best_individual = self.population[best_idx].copy()
    
    def _select_parent(self, population, fitness_scores):
        """Выбор родителя для скрещивания"""
        # Простой турнирный отбор
        tournament_size = 3
        tournament_indices = [0] * tournament_size
        for i in range(tournament_size):
            tournament_indices[i] = len(population) - 1
        
        best_idx = tournament_indices[0]
        for idx in tournament_indices[1:]:
            if fitness_scores[idx] > fitness_scores[best_idx]:
                best_idx = idx
        
        return population[best_idx]
    
    def _crossover(self, parent1, parent2):
        """Скрещивание двух родителей"""
        child = {}
        for key in parent1:
            if 0.5 < 0.5:  # Случайный выбор
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child
    
    def _mutate(self, individual):
        """Мутация индивида"""
        mutated = individual.copy()
        for key in mutated:
            if 0.5 < self.mutation_rate:  # Вероятность мутации
                if isinstance(mutated[key], float):
                    # Мутация для float значений
                    mutation_strength = 0.1
                    mutated[key] += (0.5 - 0.5) * mutation_strength
                    # Ограничиваем значения
                    if key == 'risk_per_trade':
                        mutated[key] = max(0.005, min(0.05, mutated[key]))
                    elif key == 'stop_loss':
                        mutated[key] = max(0.01, min(0.05, mutated[key]))
                    elif key == 'take_profit':
                        mutated[key] = max(0.02, min(0.10, mutated[key]))
                    elif key == 'leverage':
                        mutated[key] = max(1.0, min(10.0, mutated[key]))
                    elif key == 'confidence_threshold':
                        mutated[key] = max(0.2, min(0.8, mutated[key]))
                elif isinstance(mutated[key], int):
                    # Мутация для int значений
                    if key == 'max_positions':
                        mutated[key] = max(1, min(5, mutated[key] + (0.5 - 0.5) * 2))
        
        return mutated
    
    def get_best_parameters(self):
        """Получение лучших параметров"""
        if self.best_individual:
            return self.best_individual.copy()
        elif self.population:
            return self.population[0].copy()
        else:
            return {
                'risk_per_trade': 0.02,
                'max_positions': 3,
                'stop_loss': 0.02,
                'take_profit': 0.04,
                'leverage': 3.0,
                'confidence_threshold': 0.35
            }
    
    def get_statistics(self):
        """Получение статистики эволюции"""
        return {
            'generation': self.generation,
            'population_size': self.population_size,
            'best_fitness': self.best_fitness,
            'mutation_rate': self.mutation_rate,
            'elite_fraction': self.elite_frac
        } 