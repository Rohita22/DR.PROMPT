import React,{useState} from 'react';
import {products} from './products';
import {filterProducts} from './filter';
export default function App(){
 const [query,setQuery]=useState(''),[category,setCategory]=useState('all');
 const shown=filterProducts(products,query,category);
 return <><p className="eyebrow">THE EVERYDAY COLLECTION</p><h1>Less clutter.<br/>More possibility.</h1><p>Useful objects for thoughtful work.</p><section><div className="controls"><label>Search<input aria-label="Search products" value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Category<select aria-label="Category" value={category} onChange={e=>setCategory(e.target.value)}><option value="all">All products</option><option value="paper">Paper</option><option value="desk">Desk</option><option value="carry">Carry</option></select></label><button onClick={()=>setQuery('')}>Clear filters</button></div><p role="status">{shown.length} products</p><ul className="products">{shown.map(p=><li key={p.id}><small>{p.category}</small><h2>{p.name}</h2><p>${p.price}</p></li>)}</ul>{!shown.length&&<p data-testid="empty">No products found. Try another search.</p>}</section></>;
}
