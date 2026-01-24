/**
 * Template management utilities for chart indicator configurations
 * Stores templates in localStorage
 */

import type { IndicatorConfig } from '../types';

export interface ChartTemplate {
  id: string;
  name: string;
  indicators: IndicatorConfig[];
  createdAt: string;
  updatedAt: string;
}

const STORAGE_KEY = 'chart_templates';
const MAX_TEMPLATES = 50; // Limit number of templates to prevent storage bloat

/**
 * Get all saved templates from localStorage
 */
export function getTemplates(): ChartTemplate[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    
    const templates = JSON.parse(stored) as ChartTemplate[];
    // Validate structure
    return templates.filter(t => 
      t.id && 
      t.name && 
      Array.isArray(t.indicators)
    );
  } catch (error) {
    console.error('Error loading templates from localStorage:', error);
    return [];
  }
}

/**
 * Save a template to localStorage
 */
export function saveTemplate(name: string, indicators: IndicatorConfig[]): ChartTemplate {
  const templates = getTemplates();
  
  // Check if template name already exists
  const existingIndex = templates.findIndex(t => t.name === name);
  
  const now = new Date().toISOString();
  const template: ChartTemplate = {
    id: existingIndex >= 0 ? templates[existingIndex].id : `template-${Date.now()}`,
    name,
    indicators: [...indicators], // Create a copy
    createdAt: existingIndex >= 0 ? templates[existingIndex].createdAt : now,
    updatedAt: now,
  };

  if (existingIndex >= 0) {
    // Update existing template
    templates[existingIndex] = template;
  } else {
    // Add new template
    // Enforce max templates limit (remove oldest if needed)
    if (templates.length >= MAX_TEMPLATES) {
      templates.sort((a, b) => 
        new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      );
      templates.shift(); // Remove oldest
    }
    templates.push(template);
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
    return template;
  } catch (error) {
    console.error('Error saving template to localStorage:', error);
    throw new Error('Failed to save template. Storage may be full.');
  }
}

/**
 * Load a template by ID
 */
export function loadTemplate(id: string): ChartTemplate | null {
  const templates = getTemplates();
  return templates.find(t => t.id === id) || null;
}

/**
 * Delete a template by ID
 */
export function deleteTemplate(id: string): boolean {
  const templates = getTemplates();
  const filtered = templates.filter(t => t.id !== id);
  
  if (filtered.length === templates.length) {
    return false; // Template not found
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    return true;
  } catch (error) {
    console.error('Error deleting template from localStorage:', error);
    return false;
  }
}

/**
 * Check if a template name already exists
 */
export function templateNameExists(name: string): boolean {
  const templates = getTemplates();
  return templates.some(t => t.name === name);
}

