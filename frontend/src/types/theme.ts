export type ThemeColor = {
  primary: string;
  background: string;
  border: string;
  text: string;
  textSecondary: string;
  hover: string;
  pressed: string;
  shadow: string;
  modalShadow: string;
};

export type ThemeVariant = 'pip-boy' | 'terminal' | 'fallout3' | 'new-vegas';

export interface Theme {
  id: ThemeVariant;
  name: string;
  colors: ThemeColor;
}
