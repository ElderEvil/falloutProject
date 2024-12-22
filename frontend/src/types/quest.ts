export interface Objective {
  id: number;
  title: string;
  description: string;
  completed: boolean;
  progress?: number;
  total?: number;
}

export interface Quest {
  id: number;
  title: string;
  description: string;
  objectives: Objective[];
  status: 'active' | 'completed' | 'failed';
  reward?: {
    bottlecaps?: number;
    items?: string[];
  };
  deadline?: Date;
}
