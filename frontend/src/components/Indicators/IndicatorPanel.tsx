import { useState } from 'react';
import type { IndicatorConfig } from '../../types';

interface IndicatorPanelProps {
  indicators: IndicatorConfig[];
  onAdd: (type: 'SMA' | 'EMA', period: number) => void;
  onUpdate: (id: string, updates: Partial<IndicatorConfig>) => void;
  onRemove: (id: string) => void;
  onToggle: (id: string) => void;
}

export default function IndicatorPanel({
  indicators,
  onAdd,
  onUpdate,
  onRemove,
  onToggle,
}: IndicatorPanelProps) {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newType, setNewType] = useState<'SMA' | 'EMA'>('SMA');
  const [newPeriod, setNewPeriod] = useState(20);

  const handleAdd = () => {
    onAdd(newType, newPeriod);
    setShowAddDialog(false);
    setNewPeriod(20);
  };

  return (
    <div style={{ 
      border: '1px solid #e0e0e0', 
      borderRadius: '4px', 
      padding: '12px',
      marginBottom: '16px',
      backgroundColor: '#f9f9f9'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>Indicators</h3>
        <button
          onClick={() => setShowAddDialog(true)}
          style={{
            padding: '6px 12px',
            border: '1px solid #26a69a',
            borderRadius: '4px',
            backgroundColor: '#26a69a',
            color: 'white',
            cursor: 'pointer',
            fontSize: '14px',
          }}
        >
          + Add
        </button>
      </div>

      {showAddDialog && (
        <div style={{
          padding: '12px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          marginBottom: '12px',
          backgroundColor: 'white',
        }}>
          <div style={{ marginBottom: '8px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Type:</label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as 'SMA' | 'EMA')}
              style={{ width: '100%', padding: '4px', border: '1px solid #ccc', borderRadius: '4px' }}
            >
              <option value="SMA">SMA (Simple Moving Average)</option>
              <option value="EMA">EMA (Exponential Moving Average)</option>
            </select>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Period:</label>
            <input
              type="number"
              value={newPeriod}
              onChange={(e) => setNewPeriod(parseInt(e.target.value) || 20)}
              min="1"
              max="500"
              style={{ width: '100%', padding: '4px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleAdd}
              style={{
                padding: '6px 12px',
                border: '1px solid #26a69a',
                borderRadius: '4px',
                backgroundColor: '#26a69a',
                color: 'white',
                cursor: 'pointer',
              }}
            >
              Add
            </button>
            <button
              onClick={() => setShowAddDialog(false)}
              style={{
                padding: '6px 12px',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div>
        {indicators.map((indicator) => (
          <IndicatorItem
            key={indicator.id}
            indicator={indicator}
            onUpdate={onUpdate}
            onRemove={onRemove}
            onToggle={onToggle}
          />
        ))}
        {indicators.length === 0 && (
          <div style={{ color: '#666', fontSize: '14px', textAlign: 'center', padding: '20px' }}>
            No indicators added. Click "+ Add" to add one.
          </div>
        )}
      </div>
    </div>
  );
}

function IndicatorItem({
  indicator,
  onUpdate,
  onRemove,
  onToggle,
}: {
  indicator: IndicatorConfig;
  onUpdate: (id: string, updates: Partial<IndicatorConfig>) => void;
  onRemove: (id: string) => void;
  onToggle: (id: string) => void;
}) {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div style={{
      border: '1px solid #e0e0e0',
      borderRadius: '4px',
      padding: '8px',
      marginBottom: '8px',
      backgroundColor: indicator.visible ? 'white' : '#f5f5f5',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <input
          type="checkbox"
          checked={indicator.visible}
          onChange={() => onToggle(indicator.id)}
          style={{ cursor: 'pointer' }}
        />
        <span style={{ 
          flex: 1, 
          fontWeight: '500',
          color: indicator.visible ? '#333' : '#999',
        }}>
          {indicator.type}({indicator.period})
        </span>
        <div style={{ 
          width: '20px', 
          height: '3px', 
          backgroundColor: indicator.color,
          borderRadius: '2px',
        }} />
        <button
          onClick={() => setShowSettings(!showSettings)}
          style={{
            padding: '4px 8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            backgroundColor: 'white',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          ⚙️
        </button>
        <button
          onClick={() => onRemove(indicator.id)}
          style={{
            padding: '4px 8px',
            border: '1px solid #ef5350',
            borderRadius: '4px',
            backgroundColor: '#ef5350',
            color: 'white',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          ×
        </button>
      </div>

      {showSettings && (
        <div style={{ marginTop: '12px', padding: '12px', borderTop: '1px solid #e0e0e0' }}>
          <div style={{ marginBottom: '8px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Period:</label>
            <input
              type="number"
              value={indicator.period}
              onChange={(e) => onUpdate(indicator.id, { period: parseInt(e.target.value) || 20 })}
              min="1"
              max="500"
              style={{ width: '100%', padding: '4px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
          </div>
          <div style={{ marginBottom: '8px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Color:</label>
            <input
              type="color"
              value={indicator.color}
              onChange={(e) => onUpdate(indicator.id, { color: e.target.value })}
              style={{ width: '100%', height: '32px', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer' }}
            />
          </div>
          <div style={{ marginBottom: '8px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Line Width:</label>
            <input
              type="range"
              min="1"
              max="5"
              value={indicator.lineWidth}
              onChange={(e) => onUpdate(indicator.id, { lineWidth: parseInt(e.target.value) })}
              style={{ width: '100%' }}
            />
            <span style={{ fontSize: '12px', color: '#666' }}>{indicator.lineWidth}px</span>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px' }}>Line Style:</label>
            <select
              value={indicator.lineStyle}
              onChange={(e) => onUpdate(indicator.id, { lineStyle: e.target.value as 'solid' | 'dashed' | 'dotted' })}
              style={{ width: '100%', padding: '4px', border: '1px solid #ccc', borderRadius: '4px' }}
            >
              <option value="solid">Solid</option>
              <option value="dashed">Dashed</option>
              <option value="dotted">Dotted</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

